import asyncio
import os
import json

import psycopg2

from manager_rest import config


def print_event(event):
    try:
        print(f"\t{event['timestamp']:<26}\t{event['message']}")
    except KeyError:
        pass


def handle(conn):
    conn.poll()
    for notify in conn.notifies:
        try:
            event = json.loads(notify.payload)
        except ValueError:
            continue
        print_event(event)
    conn.notifies.clear()


def make_trigger(conn, target_table):
    with conn.cursor() as cur:
        try:
            cur.execute("""
                create trigger log_inserted
                after insert on {table}
                for each row
                execute procedure notify_new_event()
            """.format(table=target_table))
        except psycopg2.ProgrammingError:  # already exists
            conn.rollback()
        else:
            conn.commit()


def make_notify_func(conn):
    with conn.cursor() as cur:
        cur.execute("""
            create or replace function notify_new_event() returns trigger as
            $func$
                begin
                    perform pg_notify(
                        'event_inserted'::text,
                        row_to_json(NEW)::text
                    );
                    return NEW;
                end;
            $func$
            language plpgsql;
        """)
        conn.commit()


def listen(conn):
    with conn.cursor() as cur:
        cur.execute('LISTEN event_inserted')
        conn.commit()


def db_conn():
    return psycopg2.connect(
        host=config.instance.postgresql_host,
        user=config.instance.postgresql_username,
        password=config.instance.postgresql_password,
        dbname=config.instance.postgresql_db_name,
    )


def run_loop(conn):
    loop = asyncio.get_event_loop()
    loop.add_reader(conn, lambda: handle(conn))
    loop.run_forever()


if __name__ == '__main__':
    os.environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
    config.instance.load_configuration(from_db=False)
    with db_conn() as conn:
        make_notify_func(conn)
        make_trigger(conn, 'events')
        make_trigger(conn, 'logs')
        listen(conn)
        run_loop(conn)
