
import os
import sys
import tinys3


def main(access_key_id, secret_access_key, bucket, logs_dir, prefix):

    s3 = tinys3.Connection(access_key_id, secret_access_key, bucket)

    for root, dirs, files in os.walk(logs_dir):
        for log_file in files:
            abs_path = os.path.join(root, log_file)
            rel_path = abs_path[len(logs_dir) + 1:].split('/')
            test_dir = '{0}-{1}-{2}'.format(prefix, rel_path[0], rel_path[1])
            target = os.path.join('logs', test_dir, *rel_path[2:])
            if target.endswith('.log'):
                target += '.txt'
            with open(abs_path, 'rb') as f:
                s3.upload(target, f, content_type='text/plain')


if __name__ == '__main__':
    if len(sys.argv) < 6:
        print 'Usage: upload_manager_logs.py ' \
              'AWS_ACCESS_KEY_ID ' \
              'AWS_SECRET_ACCESS_KEY ' \
              'S3_BUCKET ' \
              'LOCAL_LOGS_DIR_PATH ' \
              'PREFIX_FOR_LOGS_DIR_ON_S3'
        exit(1)

    main(access_key_id=sys.argv[1],
         secret_access_key=sys.argv[2],
         bucket=sys.argv[3],
         logs_dir=sys.argv[4],
         prefix=sys.argv[5])
