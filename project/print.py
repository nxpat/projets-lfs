import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as image

import os
import re

from . import production_env

LFS_ADDRESS_1 = os.getenv("LFS_ADDRESS_1")
LFS_ADDRESS_2 = os.getenv("LFS_ADDRESS_2")
LFS_PHONE = os.getenv("LFS_PHONE")
LFS_EMAIL = os.getenv("LFS_EMAIL")
LFS_WEBSITE = os.getenv("LFS_WEBSITE").lstrip("https://").rstrip("/")


def generate_fieldtrip_pdf(data, data_path, filepath):
    # split too long data lines
    for i in range(len(data)):
        data[i][1] = "\n".join(
            re.findall(r"(.{50,}?|.{,50})(?: |\n|$)", data[i][1])
        ).removesuffix("\n")

    # set fonts
    if production_env:
        plt.rcParams["font.family"] = ["DejaVu Sans", "NanumSquareRound"]
    else:
        plt.rcParams["font.family"] = ["DejaVu Sans", "Noto Sans CJK JP"]

    # graph
    fig, ax = plt.subplots(1, figsize=(10, 10))
    ax.axis("off")

    # LFS logo
    img = "LFS_logo_couleur_transparent.png"
    img_path = data_path / img
    lfs_logo = image.imread(img_path, format="png")

    imagebox = OffsetImage(lfs_logo, zoom=0.3)
    ab1 = AnnotationBbox(imagebox, (0.0, 1.0), xybox=(0.02, 1.04), frameon=False)
    ax.add_artist(ab1)

    # AEFE logo
    img = "AEFE_logo_conventionné.gif"
    img_path = data_path / img
    aefe_logo = image.imread(img_path, format="gif")

    imagebox = OffsetImage(aefe_logo, zoom=0.5)
    ab2 = AnnotationBbox(imagebox, (0.96, 1.0), xybox=(0.92, 1.04), frameon=False)
    ax.add_artist(ab2)

    # Add title and subtitle
    plt.text(
        0.5,
        0.98,
        "Sortie scolaire",
        ha="center",
        va="center",
        fontsize=18,
        weight="bold",
    )
    plt.text(
        0.5,
        0.95,
        "(sans nuitée)",
        ha="center",
        va="center",
        fontsize=12,
    )
    plt.text(
        0.5,
        0.92,
        "Ce document vaut ordre de mission",
        ha="center",
        va="center",
        fontsize=12,
    )

    # Add a table at the bottom of the Axes
    the_table = ax.table(
        cellText=data,
        loc="center",
        cellLoc="left",
        rowLoc="left",
        colWidths=[0.4, 0.6],
        bbox=[-0.06, 0.04, 1.09, 0.8],
    )

    # Adjust cell height with number of lines
    lines = sum(len(line) // 60 + 1 for line in data[9][1].split("\n"))
    if lines > 4:
        the_table[(9, 0)].set_height(0.005 * lines)
        the_table[(9, 1)].set_height(0.005 * lines)

    # set color for last line
    the_table[(11, 0)].set_facecolor("#D4E3EC")
    the_table[(11, 1)].set_facecolor("#D4E3EC")

    # Add address, phone, and email at the bottom
    address_text = "LYCÉE FRANÇAIS DE SÉOUL"
    address_text += "\nÉtablissement homologué par le ministère français de l'Éducation nationale et conventionné avec l'AEFE"
    address_text += (
        f"\n{LFS_ADDRESS_1} | {LFS_ADDRESS_2} | {LFS_PHONE} | {LFS_EMAIL} | {LFS_WEBSITE}"
    )

    plt.figtext(0.5, 0.06, address_text, ha="center", va="center", fontsize=8)

    # plt.rcParams["font.family"] = ["DejaVu Sans"]

    fig.set_size_inches(8.267, 11.692)  # set to A4 size

    plt.savefig(filepath, dpi=300, orientation="portrait")

    # plt.show()
