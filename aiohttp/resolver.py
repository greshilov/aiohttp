import asyncio
import socket
from typing import Any, Dict, List, Type, Union

import dns
import dns.asyncresolver

from .abc import AbstractResolver

__all__ = ("ThreadedResolver", "AsyncResolver", "DefaultResolver")


class ThreadedResolver(AbstractResolver):
    """Threaded resolver.

    Uses an Executor for synchronous getaddrinfo() calls.
    concurrent.futures.ThreadPoolExecutor is used by default.
    """

    def __init__(self, use_cache: bool = False, cache_size: int = 10000) -> None:
        self._loop = asyncio.get_running_loop()

    @property
    def use_cache(self) -> bool:
        return False

    async def resolve(
        self, hostname: str, port: int = 0, family: int = socket.AF_INET
    ) -> List[Dict[str, Any]]:
        infos = await self._loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            family=family,
            flags=socket.AI_ADDRCONFIG,
        )

        hosts = []
        for family, _, proto, _, address in infos:
            if family == socket.AF_INET6:
                if len(address) < 3:
                    # IPv6 is not supported by Python build,
                    # or IPv6 is not enabled in the host
                    continue
                if address[3]:  # type: ignore[misc]
                    # This is essential for link-local IPv6 addresses.
                    # LL IPv6 is a VERY rare case. Strictly speaking, we should use
                    # getnameinfo() unconditionally, but performance makes sense.
                    host, _port = socket.getnameinfo(
                        address, socket.NI_NUMERICHOST | socket.NI_NUMERICSERV
                    )
                    port = int(_port)
                else:
                    host, port = address[:2]
            else:  # IPv4
                assert family == socket.AF_INET
                host, port = address  # type: ignore[misc]
            hosts.append(
                {
                    "hostname": hostname,
                    "host": host,
                    "port": port,
                    "family": family,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            )

        return hosts

    async def close(self) -> None:
        pass


class AsyncResolver(AbstractResolver):
    """Use the `dnspython` package to make asynchronous DNS lookups"""

    QUERY_TABLE = {
        socket.AF_INET: dns.rdatatype.A,
        socket.AF_INET6: dns.rdatatype.AAAA
    }

    def __init__(self, use_cache: bool = False, cache_size: int = 100000) -> None:
        if use_cache:
            cache = dns.resolver.LRUCache(max_size=cache_size)
        else:
            cache = None
        self._resolver = dns.asyncresolver.Resolver(configure=True)
        self._resolver.cache = cache

    @property
    def use_cache(self) -> bool:
        return self._resolver.cache is not None

    def is_cache_hit(self, host: str, family: int):
        qname = dns.name.from_text(host, None)
        rdtype = self.QUERY_TABLE[family]
        rdclass = dns.rdataclass.IN
        return self._resolver.cache.get((qname, rdtype, rdclass)) is not None

    def flush(self, host: str = None, family: int = None):
        if host is None and family is None:
            return self._resolver.cache.flush()

        qname = dns.name.from_text(host, None)
        rdtype = self.QUERY_TABLE[family]
        rdclass = dns.rdataclass.IN
        return self._resolver.cache.flush((qname, rdtype, rdclass))

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> List[Dict[str, Any]]:

        rdatatype = self.QUERY_TABLE[family]
        try:
            resp = await self._resolver.resolve(host, rdatatype, raise_on_no_answer=True)
        except dns.exception.DNSException as exc:
            raise OSError(exc.msg) from exc
        hosts = []
        for dns_record in resp:
            hosts.append(
                {
                    "hostname": host,
                    "host": dns_record.address,
                    "port": port,
                    "family": family,
                    "proto": 0,
                    "flags": socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
                }
            )

        if not hosts:
            raise OSError("DNS lookup failed")

        return hosts

    async def close(self) -> None:
        self._resolver.close()


_DefaultType = Type[Union[AsyncResolver, ThreadedResolver]]
DefaultResolver: _DefaultType = AsyncResolver
