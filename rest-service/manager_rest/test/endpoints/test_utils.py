def generate_progress_func(total_size, buffer_size=8192):
    """Generate a function that helps test upload/download progress

    :param total_size: Total size of the file to upload/download
    :param buffer_size: Size of chunk
    :return: A function that receives 2 ints - number of bytes read so far,
    and the total size in bytes
    """
    # Wrap the integer in a list, to allow mutating it inside the inner func
    iteration = [0]
    max_iterations = total_size // buffer_size

    def print_progress(*args):
        if len(args) == 2:
            read_bytes, total_bytes = args
        else:
            # This is a MultipartUploadEncoderMonitor
            read_bytes, total_bytes = args[0].bytes_read, args[0].len

        i = iteration[0]
        assert read_bytes == total_bytes

        expected_read_value = buffer_size * (i + 1)
        if i < max_iterations:
            assert read_bytes == expected_read_value
        else:
            assert read_bytes == total_bytes

        iteration[0] += 1

    return print_progress
