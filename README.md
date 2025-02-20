# Aynchronic atomic decortor in Django

### Those are the tests for the aynchronic atomic decorator in Django.
As the response to stackoverflow question: [How to use transaction with "async" functions in Django?](https://stackoverflow.com/questions/74575922/how-to-use-transaction-with-async-functions-in-django)

>If you want to use async functions in Django, you can use the `@transaction.atomic` decorator. But if you want to use async functions in Django, you can't use the `@transaction.atomic` decorator. How can I use the `@transaction.atomic` decorator with async functions in Django? See the file `asynctest.tests.test_atomic.py` for the solution.

# Tests

To test this solution, you need to have docker installed, or configure your environment to run Django tests.
We are using select_for_update to lock the row in the database and default postgresql max_connections, which is 100.
For more information, see stack overflow question: [How to use transaction with "async" functions in Django?](https://stackoverflow.com/questions/74575922/how-to-use-transaction-with-async-functions-in-django)

To run tests, run project in docker:
```bash:
docker-compose up -d --build
```

Then run tests:
```bash:
docker exec -it app pytest
```

> To see logs of the tests, see the file `test.log`