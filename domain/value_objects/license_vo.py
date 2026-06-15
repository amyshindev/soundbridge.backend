from enum import Enum


class PublicLicense(str, Enum):
    KOGL_1 = "KOGL_1"
    KOGL_2 = "KOGL_2"


LICENSE_EN_LABEL: dict[PublicLicense, str] = {
    PublicLicense.KOGL_1: "CC-BY (Commercial OK)",
    PublicLicense.KOGL_2: "CC-BY-NC (Attribution Only)",
}
LICENSE_IS_COMMERCIAL: dict[PublicLicense, bool] = {
    PublicLicense.KOGL_1: True,
    PublicLicense.KOGL_2: False,
}
