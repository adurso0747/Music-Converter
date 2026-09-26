"""`python -m music_converter` opens the GUI; with arguments it runs the CLI."""

import sys

if len(sys.argv) > 1:
    from .cli import main

    sys.exit(main())
else:
    from .gui import main

    main()
