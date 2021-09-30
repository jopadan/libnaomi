import json
import os
import struct
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

from naomi.eeprom import NaomiEEPRom


class SettingSizeEnum(Enum):
    UNKNOWN = auto()
    NIBBLE = auto()
    BYTE = auto()


class SettingType(Enum):
    UNKNOWN = auto()
    SYSTEM = auto()
    GAME = auto()


NO_FILE: str = "NO FILE"


class SettingsParseException(Exception):
    def __init__(self, msg: str, filename: str) -> None:
        super().__init__(msg)
        self.filename = filename


class SettingsSaveException(Exception):
    def __init__(self, msg: str, filename: str) -> None:
        super().__init__(msg)
        self.filename = filename


class ReadOnlyCondition:
    # A wrapper class to encapsulate that a setting is read-only based on the
    # value of another setting.

    def __init__(self, filename: str, setting: str, name: str, values: List[int], negate: bool) -> None:
        self.filename = filename
        self.setting = setting
        self.name = name
        self.values = values
        self.negate = negate

    def evaluate(self, settings: List["Setting"]) -> bool:
        for setting in settings:
            if setting.name.lower() == self.name.lower():
                if setting.current in self.values:
                    return self.negate
                else:
                    return not self.negate

        raise SettingsSaveException(
            f"The setting \"{self.setting}\" depends on the value for \"{self.name}\" but that setting does not seem to exist! Perhaps you misspelled \"{self.name}\"?",
            self.filename,
        )


class DefaultCondition:
    # A wrapper class to encapsulate one rule for a setting default.

    def __init__(self, name: str, values: List[int], negate: bool, default: int) -> None:
        self.name = name
        self.values = values
        self.negate = negate
        self.default = default


class DefaultConditionGroup:
    # A wrapper class to encapsulate a set of rules for defaulting a setting.

    def __init__(self, filename: str, setting: str, conditions: List[DefaultCondition]) -> None:
        self.filename = filename
        self.setting = setting
        self.conditions = conditions

    def evaluate(self, filename: str, name: str, settings: List["Setting"]) -> int:
        for cond in self.conditions:
            for setting in settings:
                if setting.name.lower() == cond.name.lower():
                    current = setting.current if setting.current is not None else setting.default

                    if cond.negate and current not in cond.values:
                        return cond.default
                    if not cond.negate and current in cond.values:
                        return cond.default

        namelist = list({f'"{c.name}"' for c in self.conditions})
        if len(namelist) > 2:
            namelist = [", ".join(namelist[:-1]), namelist[-1]]
        names = " or ".join(namelist)

        raise SettingsSaveException(
            f"The default for setting \"{self.setting}\" could not be determined! Perhaps you misspelled one of {names}, or you forgot a value?",
            self.filename,
        )


class Setting:
    # A single setting, complete with its name, size (and optional length if
    # the size is a byte), whether it is read-only, the allowed values for
    # the setting and finally the current value (if it has been parsed out
    # of a valid EEPROM file).

    def __init__(
        self,
        name: str,
        size: SettingSizeEnum,
        length: int,
        read_only: Union[bool, ReadOnlyCondition],
        values: Optional[Dict[int, str]] = None,
        current: Optional[int] = None,
        default: Optional[Union[int, DefaultConditionGroup]] = None,
    ) -> None:
        self.name = name
        self.size = size
        self.length = length
        self.read_only = read_only
        self.values = values or {}
        self.current = current
        self.default = default

        if size == SettingSizeEnum.UNKNOWN:
            raise Exception("Logic error!")
        if length > 1 and size != SettingSizeEnum.BYTE:
            raise Exception("Logic error!")

    def to_json(self) -> Dict[str, Any]:
        jdict = {
            'name': self.name,
            'size': self.size.name,
            'length': self.length,
            'values': self.values,
            'current': self.current,
        }

        if self.read_only is True:
            jdict['readonly'] = True
        elif self.read_only is False:
            jdict['readonly'] = False
        elif isinstance(self.read_only, ReadOnlyCondition):
            jdict['readonly'] = {
                "name": self.read_only.name,
                "values": self.read_only.values,
                "negate": self.read_only.negate,
            }

        if isinstance(self.default, int):
            jdict['default'] = self.default
        elif isinstance(self.default, DefaultConditionGroup):
            jdict['default'] = [
                {
                    "name": cond.name,
                    "values": cond.values,
                    "default": cond.default,
                    "negate": cond.negate,
                }
                for cond in self.default.conditions
            ]
        return jdict

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)

    def __repr__(self) -> str:
        return str(self)


class Settings:
    # A collection of settings as well as the type of settings this is (game versus
    # system). This is also responsible for parsing and creating sections in an actual
    # EEPROM file based on the settings themselves.

    def __init__(self, filename: str, settings: List[Setting], type: SettingType = SettingType.UNKNOWN) -> None:
        self.filename = filename
        self.settings = settings
        self.type = type

    @staticmethod
    def from_config(type: SettingType, config: "SettingsConfig", eeprom: NaomiEEPRom) -> "Settings":
        settings = config.settings
        location = 0
        halves = 0

        if type == SettingType.SYSTEM:
            data = eeprom.system
        elif type == SettingType.GAME:
            data = eeprom.game
        else:
            raise Exception(f"Cannot load settings with a config of type {type.name}!")

        for setting in settings:
            if setting.size == SettingSizeEnum.NIBBLE:
                if halves == 0:
                    setting.current = (data[location] >> 4) & 0xF
                else:
                    setting.current = data[location] & 0xF

                if halves == 0:
                    halves = 1
                else:
                    halves = 0
                    location += 1
            elif setting.size == SettingSizeEnum.BYTE:
                if halves != 0:
                    raise SettingsParseException(f"The setting \"{setting.name}\" follows a lonesome nibble. Nibble settings must always be in pairs!", config.filename)
                if setting.length == 1:
                    setting.current = struct.unpack("<B", data[location:(location + 1)])[0]
                elif setting.length == 2:
                    setting.current = struct.unpack("<H", data[location:(location + 2)])[0]
                elif setting.length == 4:
                    setting.current = struct.unpack("<I", data[location:(location + 4)])[0]
                else:
                    raise SettingsParseException(f"Cannot parse setting \"{setting.name}\" with unrecognized size \"{setting.length}\"!", config.filename)

                location += setting.length

        return Settings(config.filename, settings, type=type)

    def to_json(self) -> Dict[str, Any]:
        return {
            'type': self.type.name,
            'filename': self.filename if self.filename != NO_FILE else None,
            'settings': [
                setting.to_json() for setting in self.settings
            ],
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)

    def __repr__(self) -> str:
        return str(self)


class SettingsWrapper:
    # A wrapper class to hold both a system and game settings section together.

    def __init__(self, serial: bytes, system: Settings, game: Settings) -> None:
        self.serial = serial
        self.system = system
        self.game = game

        self.system.type = SettingType.SYSTEM
        self.game.type = SettingType.GAME

    @staticmethod
    def from_json(settings_files: Dict[str, str], jsondict: Dict[str, Any]) -> "SettingsWrapper":
        raise NotImplementedError("TODO")

    def to_json(self) -> Dict[str, Any]:
        return {
            'serial': self.serial.decode('ascii'),
            'system': self.system.to_json(),
            'game': self.game.to_json(),
        }

    def __str__(self) -> str:
        return json.dumps(self.to_json(), indent=2)

    def __repr__(self) -> str:
        return str(self)


class SettingsConfig:
    # A class that can manifest a list of settings given a particular
    # file. It is not responsible for parsing any settings. It is only
    # responsible for creating the list of settings given a settings
    # definition file.

    def __init__(self, filename: str, settings: List[Setting]) -> None:
        self.filename = filename
        self.settings = settings

    @staticmethod
    def blank() -> "SettingsConfig":
        # It would be weird to display "NO FILE" to the user when there is
        # an error, but virtually all errors arise from parsing the settings
        # file itself, so if this is blank its unlikely errors will happen.
        return SettingsConfig(NO_FILE, [])

    @staticmethod
    def __get_kv(filename: str, name: str, setting: str) -> Dict[int, str]:
        try:
            if "-" in setting:
                if " to " in setting:
                    raise SettingsParseException(
                        f"Setting \"{name}\" cannot have a range for valid values that includes a dash! \"{setting}\" should be specified like \"20 to E0\".",
                        filename,
                    )

                k, v = setting.split("-", 1)
                key = int(k.strip(), 16)
                value = v.strip()

                return {key: value}
            else:
                if " to " in setting:
                    low, high = setting.split(" to ", 1)
                    low = low.strip()
                    high = high.strip()

                    retdict: Dict[int, str] = {}
                    for x in range(int(low, 16), int(high, 16) + 1):
                        retdict[x] = f"{x}"
                    return retdict
                else:
                    key = int(setting.strip(), 16)
                    value = f"{key}"

                    return {key: value}
        except ValueError:
            raise SettingsParseException(
                f"Failed to parse setting \"{name}\", could not understand value \"{setting}\".",
                filename,
            )

    @staticmethod
    def __get_vals(filename: str, name: str, setting: str) -> Tuple[str, List[int]]:
        try:
            name, rest = setting.split(" is ", 1)
            name = name.strip()
            vals: List[int] = []

            for val in rest.split(" or "):
                vals.append(int(val, 16))

            return name, vals
        except ValueError:
            raise SettingsParseException(
                f"Failed to parse setting \"{name}\", could not understand if condition \"{setting}\".",
                filename,
            )

    @staticmethod
    def from_data(filename: str, data: str) -> "SettingsConfig":
        rawlines = data.splitlines()
        lines: List[str] = []
        settings: List[Setting] = []

        for line in rawlines:
            if not line.strip():
                # Ignore empty lines.
                continue
            if line.strip().startswith("#"):
                # Ignore comments.
                continue

            if ":" not in line:
                # Assume that this is a setting entry.
                if not lines:
                    raise SettingsParseException(f"Missing setting name before size, read-only specifier, defaults or value in \"{line}\". Perhaps you forgot a colon?", filename)

                cur = lines[-1]
                if cur.strip()[-1] == ":":
                    cur = cur + line
                else:
                    cur = cur + "," + line

                lines[-1] = cur
            else:
                # Assume that this is a full setting.
                lines.append(line)

        for line in lines:
            # First, get the name as well as the size and any restrictions.
            name, rest = line.split(":", 1)
            name = name.strip()
            rest = rest.strip()

            # Now, figure out what size it should be.
            size = SettingSizeEnum.UNKNOWN
            length = 1
            read_only: Union[bool, ReadOnlyCondition] = False
            values: Dict[int, str] = {}
            default: Optional[Union[int, DefaultConditionGroup]] = None

            if "," in rest:
                restbits = [r.strip() for r in rest.split(",")]
            else:
                restbits = [rest]

            for bit in restbits:
                if "byte" in bit or "nibble" in bit:
                    if " " in bit:
                        lenstr, units = bit.split(" ", 1)
                        length = int(lenstr.strip())
                        units = units.strip()
                    else:
                        units = bit.strip()

                    if "byte" in units:
                        size = SettingSizeEnum.BYTE
                    elif "nibble" in units:
                        size = SettingSizeEnum.NIBBLE
                    else:
                        raise SettingsParseException(f"Unrecognized unit \"{units}\" for setting \"{name}\". Perhaps you misspelled \"byte\" or \"nibble\"?", filename)
                    if size != SettingSizeEnum.BYTE and length != 1:
                        raise SettingsParseException(f"Invalid length \"{length}\" for setting \"{name}\". You should only specify a length for bytes.", filename)

                elif "read-only" in bit:
                    condstr = None
                    if " if " in bit:
                        readonlystr, condstr = bit.split(" if ", 1)
                        negate = True
                    elif " unless " in bit:
                        readonlystr, condstr = bit.split(" unless ", 1)
                        negate = False
                    else:
                        # Its unconditionally read-only.
                        read_only = True
                        readonlystr = bit

                    if readonlystr.strip() != "read-only":
                        raise SettingsParseException(f"Cannot parse read-only condition \"{bit}\" for setting \"{name}\"!", filename)
                    if condstr is not None:
                        condname, condvalues = SettingsConfig.__get_vals(filename, name, condstr)
                        read_only = ReadOnlyCondition(filename, name, condname, condvalues, negate)

                elif "default" in bit:
                    if " is " in bit:
                        defstr, rest = bit.split(" is ", 1)
                        if defstr.strip() != "default":
                            raise SettingsParseException(f"Cannot parse default \"{bit}\" for setting \"{name}\"!", filename)

                        condstr = None
                        if " if " in rest:
                            rest, condstr = rest.split(" if ", 1)
                            negate = False
                        elif " unless " in rest:
                            rest, condstr = rest.split(" unless ", 1)
                            negate = True
                        else:
                            # Its unconditionally a default.
                            pass

                        rest = rest.strip().replace(" ", "").replace("\t", "")
                        defbytes = bytes([int(rest[i:(i + 2)], 16) for i in range(0, len(rest), 2)])
                        if size != SettingSizeEnum.UNKNOWN and len(defbytes) == 1:
                            defaultint = defbytes[0]
                        else:
                            if size == SettingSizeEnum.NIBBLE:
                                defaultint = struct.unpack("<B", defbytes[0:1])[0]
                            elif size == SettingSizeEnum.BYTE:
                                if length == 1:
                                    defaultint = struct.unpack("<B", defbytes[0:1])[0]
                                elif length == 2:
                                    defaultint = struct.unpack("<H", defbytes[0:2])[0]
                                elif length == 4:
                                    defaultint = struct.unpack("<I", defbytes[0:4])[0]
                                else:
                                    raise SettingsParseException(
                                        f"Cannot convert default \"{bit}\" for setting \"{name}\" because we don't know how to handle length \"{length}\"!",
                                        filename,
                                    )
                            else:
                                raise SettingsParseException(f"Must place default \"{bit}\" after size specifier in setting \"{name}\"!", filename)

                        if condstr is None:
                            if default is not None:
                                if isinstance(default, DefaultConditionGroup):
                                    raise SettingsParseException(f"Cannot specify an unconditional default alongside conditional defaults for setting \"{name}\"!", filename)
                                else:
                                    raise SettingsParseException(f"Cannot specify more than one default for setting \"{name}\"!", filename)
                            default = defaultint
                        else:
                            if default is None:
                                default = DefaultConditionGroup(filename, name, [])
                            if not isinstance(default, DefaultConditionGroup):
                                raise SettingsParseException(f"Cannot specify an unconditional default alongside conditional defaults for setting \"{name}\"!", filename)

                            condname, condvalues = SettingsConfig.__get_vals(filename, name, condstr)
                            default.conditions.append(DefaultCondition(condname, condvalues, negate, defaultint))
                    else:
                        raise SettingsParseException(f"Cannot parse default for setting \"{name}\"! Specify defaults like \"default is 0\".", filename)

                else:
                    # Assume this is a setting value.
                    values.update(SettingsConfig.__get_kv(filename, name, bit))

            if size == SettingSizeEnum.UNKNOWN:
                raise SettingsParseException(f"Setting \"{name}\" is missing a size specifier!", filename)
            if read_only is not True and not values:
                raise SettingsParseException(f"Setting \"{name}\" is missing any valid values!", filename)

            settings.append(
                Setting(
                    name,
                    size,
                    length,
                    read_only,
                    values,
                    default=default,
                )
            )

        # Verify that nibbles come in pairs.
        halves = 0
        for setting in settings:
            if setting.size == SettingSizeEnum.NIBBLE:
                halves = 1 - halves
            elif setting.size == SettingSizeEnum.BYTE:
                if halves != 0:
                    raise SettingsParseException(f"The setting \"{setting.name}\" follows a lonesome nibble. Nibble settings must always be in pairs!", filename)

        return SettingsConfig(filename, settings)

    def defaults(self) -> bytes:
        pending = 0
        halves = 0
        defaults: List[bytes] = []

        for setting in self.settings:
            if setting.default is None:
                default = 0
            elif isinstance(setting.default, int):
                default = setting.default
            elif isinstance(setting.default, DefaultConditionGroup):
                # Must evaluate settings to figure out the default for this.
                default = setting.default.evaluate(self.filename, setting.name, self.settings)

            if setting.size == SettingSizeEnum.NIBBLE:
                if halves == 0:
                    pending = (default & 0xF) << 4
                else:
                    defaults.append(bytes([(default & 0xF) | pending]))

                if halves == 0:
                    halves = 1
                else:
                    halves = 0
            elif setting.size == SettingSizeEnum.BYTE:
                if halves != 0:
                    raise SettingsSaveException(f"The setting \"{setting.name}\" follows a lonesome nibble. Nibble settings must always be in pairs!", self.filename)
                if setting.length == 1:
                    defaults.append(struct.pack("<B", default))
                elif setting.length == 2:
                    defaults.append(struct.pack("<H", default))
                elif setting.length == 4:
                    defaults.append(struct.pack("<I", default))
                else:
                    raise SettingsSaveException(f"Cannot save setting \"{setting.name}\" with unrecognized size {setting.length}!", self.filename)

        return b"".join(defaults)


class SettingsManager:
    # A manager class that can handle manifesting and saving settings given a directory
    # of definition files.

    def __init__(self, directory: str) -> None:
        self.__directory = directory

    def __serial_to_config(self, serial: bytes) -> Optional[SettingsConfig]:
        files = {f: os.path.join(self.__directory, f) for f in os.listdir(self.__directory) if os.path.isfile(os.path.join(self.__directory, f))}
        fname = f"{serial.decode('ascii')}.settings"

        if fname not in files:
            return None

        with open(files[fname], "r") as fp:
            data = fp.read()

        return SettingsConfig.from_data(fname, data)

    def from_serial(self, serial: bytes) -> SettingsWrapper:
        config = self.__serial_to_config(serial)
        defaults = None
        if config is not None:
            defaults = config.defaults()

        return self.from_eeprom(NaomiEEPRom.default(serial, game_defaults=defaults).data)

    def from_eeprom(self, data: bytes) -> SettingsWrapper:
        # First grab the parsed EEPRom so we can get the serial.
        eeprom = NaomiEEPRom(data)

        # Now load the system settings.
        with open(os.path.join(self.__directory, "system.settings"), "r") as fp:
            systemdata = fp.read()
        systemconfig = SettingsConfig.from_data("system.settings", systemdata)

        # Now load the game settings, or if it doesn't exist, default to only
        # allowing system settings to be set.
        gameconfig = self.__serial_to_config(eeprom.serial) or SettingsConfig.blank()

        # Finally parse the EEPRom based on the config.
        system = Settings.from_config(SettingType.SYSTEM, systemconfig, eeprom)
        game = Settings.from_config(SettingType.GAME, gameconfig, eeprom)
        return SettingsWrapper(eeprom.serial, system, game)

    def from_json(self, jsondict: Dict[str, Any]) -> SettingsWrapper:
        return SettingsWrapper.from_json(
            {f: os.path.join(self.__directory, f) for f in os.listdir(self.__directory) if os.path.isfile(os.path.join(self.__directory, f))},
            jsondict,
        )

    def to_eeprom(self, settings: SettingsWrapper) -> bytes:
        # First, creat the EEPROM.
        eeprom = NaomiEEPRom.default(settings.serial)

        # Now, calculate the length of the game section, so we can create a valid
        # game chunk.
        halves = 0
        length = 0
        for setting in settings.game.settings:
            if setting.size == SettingSizeEnum.NIBBLE:
                # Update our length.
                if halves == 0:
                    halves = 1
                else:
                    halves = 0
                    length += 1

            elif setting.size == SettingSizeEnum.BYTE:
                # First, make sure we aren't in a pending nibble state.
                if halves != 0:
                    raise SettingsSaveException(f"The setting \"{setting.name}\" follows a lonesome nibble. Nibble settings must always be in pairs!", settings.game.filename)

                if setting.length not in {1, 2, 4}:
                    raise SettingsSaveException(f"Cannot save setting \"{setting.name}\" with unrecognized size {setting.length}!", settings.game.filename)

                # Update our length.
                length += setting.length

        # Now, update the game length.
        eeprom.length = length

        for section, settingsgroup in [
            (eeprom.system, settings.system),
            (eeprom.game, settings.game),
        ]:
            pending = 0
            halves = 0
            location = 0

            if not section.valid:
                # If we couldn't make this section correct, completely skip out on it.
                continue

            for setting in settingsgroup.settings:
                # First, calculate what the default should be in case we need to use it.
                if setting.default is None:
                    default = None
                elif isinstance(setting.default, int):
                    default = setting.default
                elif isinstance(setting.default, DefaultConditionGroup):
                    # Must evaluate settings to figure out the default for this.
                    default = setting.default.evaluate(settingsgroup.filename, setting.name, settingsgroup.settings)

                # Now, figure out if we should defer to the default over the current value
                # (if it is read-only) or if we should use the current value.
                if isinstance(setting.read_only, ReadOnlyCondition):
                    read_only = setting.read_only.evaluate(settingsgroup.settings)
                elif setting.read_only is True:
                    read_only = True
                elif setting.read_only is False:
                    read_only = False

                if read_only:
                    # If it is read-only, then only take the current value if the default doesn't
                    # exist. This lets settings that are selectively read-only get a conditional
                    # default if one exists that takes precedence over the current value.
                    value = setting.current if default is None else default
                else:
                    # If the setting is not read-only, then only take the default if the current
                    # value is None.
                    value = default if setting.current is None else setting.current

                # Now, write out the setting by updating the EEPROM in the correct location.
                if setting.size == SettingSizeEnum.NIBBLE:
                    # First, if we have anything to write, write it.
                    if value is not None:
                        if halves == 0:
                            pending = (value & 0xF) << 4
                        else:
                            section[location] = (value & 0xF) | pending

                    # Now, update our position.
                    if halves == 0:
                        halves = 1
                    else:
                        halves = 0
                        location += 1

                elif setting.size == SettingSizeEnum.BYTE:
                    # First, make sure we aren't in a pending nibble state.
                    if halves != 0:
                        raise SettingsSaveException(f"The setting \"{setting.name}\" follows a lonesome nibble. Nibble settings must always be in pairs!", settingsgroup.filename)

                    if setting.length not in {1, 2, 4}:
                        raise SettingsSaveException(f"Cannot save setting \"{setting.name}\" with unrecognized size {setting.length}!", settingsgroup.filename)

                    if value is not None:
                        if setting.length == 1:
                            section[location:(location + 1)] = struct.pack("<B", value)
                        elif setting.length == 2:
                            section[location:(location + 2)] = struct.pack("<H", value)
                        elif setting.length == 4:
                            section[location:(location + 4)] = struct.pack("<I", value)

                    # Now, update our position.
                    location += setting.length

        return eeprom.data
