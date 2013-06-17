import psycopg2.extensions
import psycopg2.pool
import sys

import gevent
import gevent.coros
from gevent.socket import wait_read, wait_write

def gevent_wait_callback(conn, timeout=None):
    """A wait callback useful to allow gevent to work with Psycopg."""

    while True:
        state = conn.poll()
        if state == psycopg2.extensions.POLL_OK:
            break
        elif state == psycopg2.extensions.POLL_READ:
            #print 'Greenlet waiting on READ'
            wait_read(conn.fileno(), timeout=timeout)
        elif state == psycopg2.extensions.POLL_WRITE:
            #print 'Greenlet waiting on WRITE'
            wait_write(conn.fileno(), timeout=timeout)
        else:
            raise psycopg2.OperationalError(
                "Bad result from poll: %r" % state)

class GeventConnectionPool(psycopg2.pool.AbstractConnectionPool):
    def __init__(self, minconn, maxconn, *args, **kwargs):
        self.semaphore = gevent.coros.Semaphore(maxconn)
        psycopg2.pool.AbstractConnectionPool.__init__(self, minconn, maxconn, *args, **kwargs)

    def getconn(self, *args, **kwargs):
        self.semaphore.acquire()
        return self._getconn(*args, **kwargs)

    def putconn(self, *args, **kwargs):
        self._putconn(*args, **kwargs)
        self.semaphore.release()

    # Not sure what to do about this one...
    closeall = psycopg2.pool.AbstractConnectionPool._closeall


def main(db_name):
    psycopg2.extensions.set_wait_callback(gevent_wait_callback)
    pool = GeventConnectionPool(5, 40, database=db_name)

    def use_connection(count):
        conn = pool.getconn()
        cur = conn.cursor()
        #gevent.sleep(5)
        cur.execute("SELECT 2 + 2")
        print '{}: {}'.format(count, cur.fetchone()[0])
        pool.putconn(conn)

    gevent.joinall([gevent.spawn(use_connection, i) for i in xrange(1000)])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print 'You must supply the database name:\n  $ pypy {} db_name'.format(sys.argv[0])
        sys.exit(1)
    main(sys.argv[1])
