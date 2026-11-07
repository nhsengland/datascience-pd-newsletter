"""Check files and prepare them for Notify's send-a-file-by-email feature."""

from pathlib import Path

from notifications_python_client import prepare_upload
from notifications_python_client.utils import DOCUMENT_UPLOAD_SIZE_LIMIT

ALLOWED_SUFFIXES = frozenset(
    {".csv", ".doc", ".docx", ".jpeg", ".jpg", ".json", ".odt", ".pdf", ".png"}
    | {".rtf", ".txt", ".xlsx"}
)
MAX_FILENAME_LENGTH = 100
MAX_RETENTION_WEEKS = 78


class FileError(ValueError):
    """Raised when a file cannot be sent through Notify."""


def check_file(path: Path) -> None:
    """Check a file exists and Notify will accept its type, size and name.

    Parameters
    ----------
    path : Path
        File to send.

    Raises
    ------
    FileError
        If the file is missing, too big, has a long name or an unsupported type.
    """
    if not path.is_file():
        raise FileError(f"No file at {path}")
    suffix = path.suffix.lower()
    if suffix == ".log":
        raise FileError(f"{path.name}: Notify does not accept .log files. Save as .txt")
    if suffix not in ALLOWED_SUFFIXES:
        raise FileError(
            f"{path.name}: Notify only accepts {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )
    size = path.stat().st_size
    if size > DOCUMENT_UPLOAD_SIZE_LIMIT:
        raise FileError(f"{path.name} is {size:,} bytes; Notify's limit is 2MB")
    if len(path.name) > MAX_FILENAME_LENGTH:
        raise FileError(
            f"{path.name}: the name must be {MAX_FILENAME_LENGTH} characters or fewer"
        )


def prepare_file(
    path: Path, confirm_email: bool = True, retention_weeks: int = 26
) -> dict:
    """Check and encode a file once, ready to attach to any number of emails.

    Recipients get a link to download the file, not an attachment.

    Parameters
    ----------
    path : Path
        File to send.
    confirm_email : bool
        Whether recipients must enter their email address before downloading.
        Keep this on for personal, sensitive or OFFICIAL information.
    retention_weeks : int
        How long the file stays available, from 1 to 78 weeks.

    Returns
    -------
    dict
        Value for the template's ``((link_to_file))`` placeholder.

    Raises
    ------
    FileError
        If the file or settings are not accepted.
    """
    check_file(path)
    if not 1 <= retention_weeks <= MAX_RETENTION_WEEKS:
        raise FileError(f"retention_weeks must be from 1 to {MAX_RETENTION_WEEKS}")
    unit = "week" if retention_weeks == 1 else "weeks"
    with path.open("rb") as file:
        return prepare_upload(
            file,
            filename=path.name,
            confirm_email_before_download=confirm_email,
            retention_period=f"{retention_weeks} {unit}",
        )
