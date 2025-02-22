from asgiref.sync import sync_to_async, async_to_sync
from concurrent.futures import ThreadPoolExecutor
from asyncio import gather, wrap_future, sleep
from django.db.utils import OperationalError
from django.db.transaction import Atomic
from django.db import connections
from ..models import MyModel
from random import randint
from typing import Union
from time import time_ns
import logging
import pytest
import asyncio
import logging


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('asynctest.tests')


class AsyncAtomicContextManager(Atomic):
    """To async use atomic context, you need to use run_in_context on db related methods."""

    def __init__(self, using=None, savepoint=True, durable=False):
        super().__init__(using, savepoint, durable)
        self.executor = ThreadPoolExecutor(1)

    async def __aenter__(self):
        await sync_to_async(super().__enter__, thread_sensitive=False, executor=self.executor)()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await sync_to_async(super().__exit__, thread_sensitive=False, executor=self.executor)(exc_type, exc_value, traceback)
        future = wrap_future(self.executor.submit(self.close_connections))
        await future
        self.executor.shutdown()

    async def run_in_context(self, fun, *args, **kwargs):
        """Use this method to run db related methods in atomic context."""
        future = wrap_future(self.executor.submit(fun, *args, **kwargs))
        await future
        return future.result()
    
    def close_connections(self):
        """It is necessary to close connections before shutdown."""
        for conn in connections.all():
            conn.close()

def aatomic(using=None, savepoint=True, durable=False):
    """This decorator will run function in new atomic context. Which will be destroyed after function ends."""
    def decorator(fun):
        async def wrapper(*args, **kwargs):
            async with AsyncAtomicContextManager(using, savepoint, durable) as aacm:
                future = wrap_future(aacm.executor.submit(async_to_sync(fun), *args, **kwargs))
                await future
                return future.result()
        return wrapper
    return decorator

@aatomic()
async def async_select_for_update__decorator(pk: int, number: int):
    logger.info(f'{number} decorator: Started.')
    await sleep(randint(0, 100)/10000)
    obj = await MyModel.objects.select_for_update().aget(pk=pk)
    logger.info(f'{number} decorator: Got object in, saved {obj.saved} times.')
    await sleep(0.005)
    await obj.asave()
    logger.info(f'{number} decorator: Finished.')

async def async_select_for_update__context_manager(pk: int, number: int) -> Union[Exception, None]:
    try:
        async with AsyncAtomicContextManager() as aacm:
            logger.info(f'{number} context_manager: Started.')
            await sleep(randint(0, 100)/10000)
            obj = await aacm.run_in_context(MyModel.objects.select_for_update().get, pk=pk)
            logger.info(f'{number} context_manager: Got object in, saved {obj.saved} times.')
            await sleep(0.005)
            await aacm.run_in_context(obj.save)
            logger.info(f'{number} context_manager: Finished.')
    except Exception as e:
        logger.error(f'{number} context_manager: {str(e).strip()}')
        return e

async def handle_errors_outside_decorator(pk: int, number: int) -> Union[Exception, None]:
    """for decorator we have to handle exceptions outside tested method."""
    try:
        await async_select_for_update__decorator(pk, number)
    except Exception as e:
        logger.error(f'{number} decorator: {str(e).strip()}')
        return e

@pytest.mark.django_db(transaction=True)
def test_will_throw_error_for_too_many_connections__context_manager(event_loop: asyncio.BaseEventLoop):
    logger.debug("[STARTING TEST] test_will_throw_error_for_too_many_connections__context_manager")
    pk = MyModel.objects.create().pk
    start = time_ns()
    results = event_loop.run_until_complete(gather(
        *[async_select_for_update__context_manager(pk, i) for i in range(200)]
    ))
    logger.debug(f'context_manager too many test: Finished in {(time_ns() - start)/1_000_000_000} seconds)')
    assert len([
        result for result in results
        if isinstance(result, OperationalError)
        and str(result).find('too many clients already') != -1
    ]), 'Expected error for too many clients in db. We are running 200 tasks and Postgres has default limit of 100.'
    assert len([
        result for result in results
        if not isinstance(result, OperationalError)
        and not isinstance(result, Exception)
    ]), 'Tasks below limit should finish graefully.'
    logger.debug('\n')

@pytest.mark.django_db(transaction=True)
def test_will_throw_error_for_too_many_connections__decorator(event_loop: asyncio.BaseEventLoop):
    logger.debug("[STARTING TEST] test_will_throw_error_for_too_many_connections__decorator")
    pk = MyModel.objects.create().pk
    start = time_ns()
    results = event_loop.run_until_complete(gather(
        *[handle_errors_outside_decorator(pk, i) for i in range(200)]
    ))
    logger.debug(f'decorator too many test: Finished in {(time_ns() - start)/1_000_000_000} seconds)')
    assert len([
        result for result in results
        if isinstance(result, OperationalError)
        and str(result).find('too many clients already') != -1
    ]), 'Expected error for too many clients in db. We are running 200 tasks and Postgres has default limit of 100.'
    assert len([
        result for result in results
        if not isinstance(result, OperationalError)
        and not isinstance(result, Exception)
    ]), 'Tasks below limit should still finish graefully.'
    logger.debug('\n')

@pytest.mark.django_db(transaction=True)
def test_will_finish_gracefully(event_loop: asyncio.BaseEventLoop):
    logger.debug("[STARTING TEST] test_will_finish_gracefully")
    pk = MyModel.objects.create().pk
    start = time_ns()
    results = event_loop.run_until_complete(gather(
        *[async_select_for_update__context_manager(pk, i) for i in range(45)],
        *[handle_errors_outside_decorator(pk, i) for i in range(45)]
    ))
    logger.debug(f'finish gracefully test: Finished in {(time_ns() - start)/1_000_000_000} seconds)')
    assert not len([
        result for result in results
        if isinstance(result, OperationalError)
        and str(result).find('too many clients already') != -1
    ]), 'There should be no error. We are running 90 tasks and Postgres has default limit of 100.'
    logger.debug('\n')
