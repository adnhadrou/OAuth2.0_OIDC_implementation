# Case study: a code-redemption race and its fix

## Failure being investigated

A deliberately unsafe check-then-set implementation reads `consumed=false`, signs tokens and later marks the code used without a transaction lock. Two requests can both read the unused value. A sequential replay test passes because the second request arrives after the write, concealing the race.

`tests/test_race_exercise.py` isolates this introduced flaw using a barrier that ensures both workers read the same initial value. It contains no network endpoint or production toggle. Its test succeeds when it demonstrates two unsafe successes. This is an educational fixture, not a discovered vulnerability in a third-party product and not a CVE claim.

## Fix and reasoning

`authorization.py:token` obtains `SELECT ... FOR UPDATE`, verifies every binding, sets consumed and signs tokens while the PostgreSQL transaction owns the row. `common.py` commits before returning the response. A competing request waits and then observes the updated state. Invalid binding attempts cannot consume or revoke another client's code. Correctly bound reuse revokes the grant, which the API checks on every request.

The real integration test releases eight separate Flask requests/connections at the same barrier. It requires exactly one HTTP 200 and seven invalid-grant responses, then verifies persisted consumption. This tests PostgreSQL locking, not just Python thread scheduling or a mocked flag. Browser tests and Authlib interoperability cover other parts of the flow; they do not replace this race test.

See [observed results](test-results.md) for whether this regression ran in the reported environment. No timing or throughput conclusions are drawn from the test.

Tradeoff: a crash after commit but before token delivery requires restarting the login flow. Holding the code lock during signing increases transaction duration slightly. Immediate revocation makes API availability depend on PostgreSQL. Those choices are acceptable and explicit for this small lab.

