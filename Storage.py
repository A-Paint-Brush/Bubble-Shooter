"""Classes for storing complex structures in memory and doing threaded disk IO."""
from Util import find_abs_path, get_platform_data_path
import typing as tp
import threading
import queue
import enum
import csv
import os
status_codes = enum.Enum("status_codes", "SUCCESS ERROR")


class AchievementData:
    def __init__(self):
        """Stores the message-string and state of each achievement in memory."""
        self.titles = ()
        self.body_text = ()
        self.explanation_text = ()
        # Stores the IDs of all acquired achievements.
        self.achievements: tp.Optional[tp.List[bool]] = None
        self.db_binding: tp.Optional[tp.Callable[[int], None]] = None

    def load_achievements(self, loaded_data: tp.List[bool], binding: tp.Callable[[int], None]) -> None:
        self.achievements = loaded_data
        self.db_binding = binding

    def get_new_achievement(self, achievement_id: int) -> tp.Tuple[str, str]:
        self.achievements[achievement_id] = True
        self.db_binding(achievement_id)
        return self.titles[achievement_id], self.body_text[achievement_id]

    def get_state_data(self) -> tp.List[bool]:
        return self.achievements

    def get_achievement_string(self, achievement_id: int) -> tp.Tuple[str, str]:
        return self.titles[achievement_id], self.explanation_text[achievement_id]

    def has_achievement(self, achievement_id: int) -> bool:
        return self.achievements[achievement_id]

    def get_achievement_len(self) -> int:
        return len(self.titles)


class HelpFile:
    def __init__(self):
        self.file_path = find_abs_path("./Help/Instructions.txt")
        self.encoding = "utf-8"
        self.error_text = ("Failed to load instructions :(\n\nThis could be because the help file has been "
                           "moved/deleted, the OS or an anti-virus program is blocking this game from accessing it, or "
                           "due to a hardware error (such as a faulty hard-disk).")
        self.data_queue = queue.Queue()
        self.io_thread = threading.Thread(target=self.start_file_read, daemon=True)
        self.io_thread.start()

    def start_file_read(self) -> None:
        if not os.path.isfile(self.file_path):
            self.data_queue.put((status_codes.ERROR, None))
            return None
        try:
            with open(self.file_path, "r", encoding=self.encoding) as file:
                text_data = file.read()
        except OSError:
            self.data_queue.put((status_codes.ERROR, None))
        else:
            self.data_queue.put((status_codes.SUCCESS, text_data))

    def is_running(self) -> bool:
        return self.io_thread.is_alive()

    def get_data(self) -> str:
        """Only call this after 'HelpFile.is_done' returns True."""
        status, data = self.data_queue.get()
        if status == status_codes.SUCCESS:
            return data
        elif status == status_codes.ERROR:
            return self.error_text


class ScoreDB:
    def __init__(self):
        self.dir_path = get_platform_data_path("global")
        self.file_path = os.path.join(self.dir_path, "scoreboard.csv")
        self.encoding = "utf-8"
        self.fields = ("player-name", "score")
        self.data_queue = queue.Queue()
        self.io_thread: tp.Optional[threading.Thread] = None

    def is_busy(self) -> bool:
        return self.io_thread.is_alive()

    def get_data(self) -> tp.Tuple[enum.Enum, tp.Optional[tp.List[tp.Dict[str, str]]]]:
        if not self.io_thread.is_alive():
            return self.data_queue.get()

    def write_config_file(self) -> bool:
        try:
            if not os.path.isdir(self.dir_path):
                os.mkdir(self.dir_path)
            with open(self.file_path, "w", encoding=self.encoding, newline="") as file:
                writer = csv.DictWriter(file, self.fields)
                writer.writeheader()
        except OSError:
            return False
        else:
            return True

    def start_fetch_scores(self) -> None:
        self.io_thread = threading.Thread(target=self.fetch_scores)
        self.io_thread.start()

    def fetch_scores(self) -> None:
        if not os.path.isfile(self.file_path) and not self.write_config_file():
            # Scoreboard DB not found and cannot be created. Return 'success' so the game can try to write the current
            # score to the DB.
            self.data_queue.put((status_codes.SUCCESS, []))
        try:
            with open(self.file_path, "r", encoding=self.encoding, newline="") as file:
                reader = csv.DictReader(file, self.fields)
                try:
                    next(reader)  # Skip header
                except StopIteration:  # Unexpected EOF.
                    if self.write_config_file():  # Attempt to over-write the malformed file.
                        # Overwrite successful, DB is now empty.
                        self.data_queue.put((status_codes.SUCCESS, []))
                    else:
                        # DB file is still corrupted, return error.
                        self.data_queue.put((status_codes.ERROR, None))
                    return None
                else:
                    csv_data = list(reader)
        except OSError:
            self.data_queue.put((status_codes.ERROR, None))
        else:
            self.data_queue.put((status_codes.SUCCESS, csv_data))

    def start_write_score(self, player_name: str, score: int) -> None:
        self.io_thread = threading.Thread(target=self.write_score, args=(player_name, score))
        self.io_thread.start()

    def write_score(self, player_name: str, score: int) -> None:
        """Starts the write operation to insert the data given to the beginning of the DB."""
        if not os.path.isfile(self.file_path) and not self.write_config_file():
            return None
        try:
            with open(self.file_path, "r", encoding=self.encoding, newline="") as file:
                reader = csv.DictReader(file, self.fields)
                csv_data = list(reader)
            if not csv_data or csv_data[0] != {self.fields[0]: self.fields[0], self.fields[1]: self.fields[1]}:
                return None  # Malformed data.
            csv_data.insert(1, {self.fields[0]: player_name, self.fields[1]: score})
            with open(self.file_path, "w", encoding=self.encoding, newline="") as file:
                writer = csv.DictWriter(file, self.fields)
                writer.writerows(csv_data)
        except OSError:
            return None


class AchievementDB:
    def __init__(self, achievement_length: int):
        """Synchronizes achievement data with the hard disk. The disk IO is done in a different thread that runs
        alongside the game, and it will end when the main-thread ends."""
        # task_types = enum.Enum("task_types", "ALIVE_PING")
        self.achievement_length = achievement_length
        self.default_data = [False] * self.achievement_length
        self.parent_dir = get_platform_data_path("user")
        self.file_path = os.path.join(self.parent_dir, "achievements.bin")
        self.pending_tasks = queue.Queue()
        self.writer = threading.Thread(target=self.writer_thread)
        self.writer.start()

    @staticmethod
    def encode_booleans(original_booleans: tp.List[bool]) -> bytes:
        if not original_booleans:  # Return empty bytes object if list is empty
            return b""
        dec_num = int("".join(str(int(i)) for i in original_booleans), base=2)
        full_bytes, remaining_bits = divmod(len(original_booleans), 8)
        byte_length = full_bytes + bool(remaining_bits)
        return dec_num.to_bytes(byte_length, "big")

    @staticmethod
    def decode_booleans(encoded_bytes: bytes, bool_len: int) -> tp.List[bool]:
        return [bool(int(binary_digit))
                for binary_digit in bin(int(encoded_bytes.hex() or "0", base=16))[2:bool_len + 2].zfill(bool_len)]

    def ensure_exists(self) -> bool:
        if os.path.isfile(self.file_path):
            return True
        if not os.path.isdir(self.parent_dir):
            try:
                os.mkdir(self.parent_dir)
            except OSError:
                return False
        try:
            with open(self.file_path, "wb") as file:
                file.write(self.encode_booleans(self.default_data))
        except OSError:
            return False
        else:
            return True

    def read_data(self) -> tp.Optional[tp.List[bool]]:
        if not self.ensure_exists():
            return None
        try:
            with open(self.file_path, "rb") as file:
                data = file.read()
        except OSError:
            return None
        else:
            return self.decode_booleans(data, self.achievement_length)

    def write_data(self, updated_data: tp.List[bool]) -> None:
        try:
            with open(self.file_path, "wb") as file:
                file.write(self.encode_booleans(updated_data))
        except OSError:
            return None

    def set_achievement(self, index: int) -> None:
        """Schedules user achievement data on the disk to be updated."""
        self.pending_tasks.put(index)

    def writer_thread(self) -> None:
        while True:
            try:
                index = self.pending_tasks.get(timeout=1)
            except queue.Empty:
                index = None  # Queue is empty
            if index is None:
                main_td = threading.main_thread()
                if not main_td.is_alive():
                    break  # End thread is all tasks are done and the main thread has exited.
            else:
                self.update_data(index)

    def update_data(self, index: int) -> None:
        stored_data = self.read_data()
        if stored_data is None:
            return None
        stored_data[index] = True
        self.write_data(stored_data)
