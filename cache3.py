#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""Simple Cache in the form of a Key-Value Store (KVS) like Redis, based on
SQLite, optionally supporting expiration of keys. No detailed error handling
here. If the cache does not work, we (currently) don't report the reason and
simply return `False`.

>>> cache3.get('session-key')
False
>>> cache3.set('session-key', '123abc', expire=time3.now() + 5)
True
>>> cache3.get('session-key')
u'123abc'
>>> time.sleep(6)
>>> cache3.get('session-key')
False
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021601'

from . import time3
from . import db_sqlite3


def get(key, as_dict=False, path='', filename='linuxfabrik-plugin-cache.db'):
    """Get the value of key. If the key does not exist, `False` is returned.

    Parameters
    ----------
    key : str
        The search key.

    Returns
    -------
    str or bool
        The value that belongs to the key, `False` if not found or on
        failure.
    """

    success, conn = db_sqlite3.connect(path=path, filename=filename)
    if not success:
        return False

    success, result = db_sqlite3.select(
        conn,
        sql='SELECT key, value, timestamp FROM cache WHERE key = :key;',
        data={'key': key}, fetchone=True
    )
    if not success:
        # error accessing or querying the cache
        db_sqlite3.close(conn)
        return False

    if not result or result is None:
        # key not found
        db_sqlite3.close(conn)
        return False

    if result['timestamp'] != 0 and result['timestamp'] <= time3.now():
        # key was found, but timstamp was set and has expired:
        # delete all expired keys and return false
        success, result = db_sqlite3.delete(
            conn,
            sql='DELETE FROM cache WHERE timestamp <= {};'.format(time3.now())
        )
        success, result = db_sqlite3.commit(conn)
        db_sqlite3.close(conn)
        return False

    # return the value
    db_sqlite3.close(conn)

    if not as_dict:
        # just return the value (as used to when for example using Redis)
        return result['value']
    # return all columns
    return result


def set(key, value, expire=0, path='', filename='linuxfabrik-plugin-cache.db'):
    """Set key to hold the string value.

    Keys have to be unique. If the key already holds a value, it is
    overwritten, including the expire timestamp in seconds.

    Parameters
    ----------
    key : str
        The key.
    value : str
        The value. Always stored as string.
    expire : int
        Set the expire unix timestamp, in seconds. If 0 (default), key never
        expires.

    Returns
    -------
    bool
        `True` on success, `False` on failure.
    """

    success, conn = db_sqlite3.connect(path=path, filename=filename)
    if not success:
        return False

    definition = '''
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            timestamp   INT NOT NULL
        '''
    success, result = db_sqlite3.create_table(conn, definition, table='cache')
    if not success:
        db_sqlite3.close(conn)
        return False

    success, result = db_sqlite3.create_index(conn, column_list='key', table='cache', unique=True)
    if not success:
        db_sqlite3.close(conn)
        return False

    data = {
        'key': key,
        'value': value,
        'timestamp': expire,
    }

    success, result = db_sqlite3.replace(conn, data, table='cache')
    if not success:
        db_sqlite3.close(conn)
        return False

    success, result = db_sqlite3.commit(conn)
    db_sqlite3.close(conn)
    if not success:
        return False

    return True
