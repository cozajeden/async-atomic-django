# Aynchronic atomic decorator in Django

### Those are the tests for the aynchronic atomic decorator in Django.
As the response to stackoverflow question: [How to use transaction with "async" functions in Django?](https://stackoverflow.com/questions/74575922/how-to-use-transaction-with-async-functions-in-django)

### The solution is to run the async function in a thread with different database connection.
To achieve this we need to use another thread with different context, which will result in a different database connection.
It also rquire to close the connection after the thread is finished, to avoid the hanging connection. Here is our solution:

#### The context manager:
```python
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
        await sleep(1)

    async def run_in_context(self, fun, *args, **kwargs):
        """Use this method to run db related methods in atomic context."""
        future = wrap_future(self.executor.submit(fun, *args, **kwargs))
        await future
        return future.result()
    
    def close_connections(self):
        """It is necessary to close connections before shutdown."""
        for conn in connections.all():
            conn.close()
```

#### The decorator:
```python
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
```

# Tests

To test this solution, you need to have docker installed, or configure your environment to run Django tests.
We are using select_for_update to lock the row in the database and default postgresql max_connections, which is 100.

> Test file: ``asynctest/tests/test_atomic.py``

To run tests, run project in docker:
```bash
docker-compose up -d --build
```

Then run tests:
```bash
docker exec -it app pytest
```

> To see the test logs, see the file `test.log`.