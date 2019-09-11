""" Dask Distributed Tools

"""
from typing import Any, Iterable, Optional
from random import randint
import toolz
import queue
from dask.distributed import Client
import dask
import threading
import logging

__all__ = (
    "start_local_dask",
    "pmap",
    "compute_tasks",
    "partition_map",
)

_LOG = logging.getLogger(__name__)


def start_local_dask(n_workers: int = 1,
                     threads_per_worker: Optional[int] = None,
                     mem_safety_margin: Optional[int] = None,
                     **kw):
    """Wrapper around `distributed.Client(..)` constructor that deals with memory better.

    :param n_workers: number of worker processes to launch
    :param threads_per_worker: number of threads per worker, default is as many as there are CPUs
    :param mem_safety_margin: bytes to reserve for the rest of the system, only applicable
                              if `memory_limit=` is not supplied.

    NOTE: if `memory_limit` is supplied, it will passed on to `distributed.Client`
    unmodified. It applies per worker not per whole cluster, so if you have
    `n_workers > 1`, total cluster memory will then be `n_workers*memory_limit`
    you should take that into account.
    """

    mem = kw.pop('memory_limit', None)
    if mem is None:
        from psutil import virtual_memory
        total_bytes = virtual_memory().total
        if mem_safety_margin is None:
            # Default to 500Mb or half of all memory if there is less than 1G of RAM
            mem_safety_margin = min(500*(1024*1024), total_bytes//2)

        mem = (total_bytes - mem_safety_margin)//n_workers

    client = Client(n_workers=n_workers,
                    threads_per_worker=threads_per_worker,
                    memory_limit=mem,
                    **kw)

    return client


def _randomize(prefix):
    return '{}-{:08x}'.format(prefix, randint(0, 0xFFFFFFFF))


def partition_map(n: int, func: Any, its: Iterable[Any],
                  name: str = 'compute') -> Iterable[Any]:
    """ Partition sequence into lumps of size `n`, then construct dask delayed computation evaluating to:

    [func(x) for x in its[0:1n]],
    [func(x) for x in its[n:2n]],
    ...
    [func(x) for x in its[]],

    :param n: number of elements to process in one go
    :param func: Function to apply (non-dask)
    :param its:  Values to feed to fun
    :param name: How the computation should be named in dask visualizations
    """
    def lump_proc(dd):
        return [func(d) for d in dd]

    proc = dask.delayed(lump_proc, nout=1, pure=True)
    data_name = _randomize('data_' + name)
    name = _randomize(name)

    for i, dd in enumerate(toolz.partition_all(n, its)):
        lump = dask.delayed(dd,
                            pure=True,
                            traverse=False,
                            name=data_name + str(i))
        yield proc(lump, dask_key_name=name + str(i))


def compute_tasks(tasks: Iterable[Any], client: Client,
                  max_in_flight: int = 3) -> Iterable[Any]:
    """ Parallel compute stream with back pressure.

        Equivalent to:

        (client.compute(task).result()
          for task in tasks)

        but with up to `max_in_flight` tasks being processed at the same time.
        Input/Output order is preserved, so there is a possibility of head of
        line blocking.

        NOTE: lower limit is 3 concurrent tasks to simplify implementation,
              there is no point calling this function if you want one active
              task and supporting exactly 2 active tasks is not worth the complexity,
              for now. We might special-case `2` at some point.

    """
    # New thread:
    #    1. Take dask task from iterator
    #    2. Submit to client for processing
    #    3. Send it of to wrk_q
    #
    # Calling thread:
    #    1. Pull scheduled future from wrk_q
    #    2. Wait for result of the future
    #    3. yield result to calling code
    from .generic import it2q, qmap

    # (max_in_flight - 2) -- one on each side of queue
    wrk_q = queue.Queue(maxsize=max(1, max_in_flight - 2))  # type: queue.Queue

    # fifo_timeout='0ms' ensures that priority of later tasks is lower
    futures = (client.compute(task, fifo_timeout='0ms') for task in tasks)

    in_thread = threading.Thread(target=it2q, args=(futures, wrk_q))
    in_thread.start()

    yield from qmap(lambda f: f.result(), wrk_q)

    in_thread.join()


def pmap(func: Any,
         its: Iterable[Any],
         client: Client,
         lump: int = 1,
         max_in_flight: int = 3,
         name: str = 'compute') -> Iterable[Any]:
    """ Parallel map with back pressure.

    Equivalent to this:

       (func(x) for x in its)

    Except that ``func(x)`` runs concurrently on dask cluster.

    :param func:   Method that will be applied concurrently to data from ``its``
    :param its:    Iterator of input values
    :param client: Connected dask client
    :param lump:   Group this many datasets into one task
    :param max_in_flight: Maximum number of active tasks to submit
    :param name:   Dask name for computation
    """
    max_in_flight = max_in_flight // lump

    tasks = partition_map(lump, func, its, name=name)

    for xx in compute_tasks(tasks, client=client, max_in_flight=max_in_flight):
        yield from xx