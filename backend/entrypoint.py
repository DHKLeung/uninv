"""PyInstaller entrypoint for uninv backend."""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from uninv_backend import main

    main()
