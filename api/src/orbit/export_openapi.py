"""Print the API's OpenAPI schema as stable, pretty JSON (input to the web app's type generation).

Run:  uv run python -m orbit.export_openapi > ../web/src/lib/api/openapi.json
Normally called by scripts/gen-api-types.sh.
"""

import json
import sys

from orbit.core.config import Settings
from orbit.main import create_app


def main() -> None:
    # Defaults only: the schema must not depend on whoever runs this.
    app = create_app(Settings(_env_file=None, app_env="development"))
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
