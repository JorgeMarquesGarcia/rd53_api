from pathlib import Path
import logging

# Ajusta estos imports a tu estructura real
from rd53_api.config.txt.txt_manager import TxtManager, SaveMode



# --------------------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------------------

BASE_DIR = Path(
    r"C:\Users\jmarques\Containers\RD53\RD53_analysis\ConfigFiles"
)

CHIP_ID = "F7"   # ejemplo: F7, H4, F5, etc.


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("txt_test")


# --------------------------------------------------
# MOCK DE PÍXELES RUIDOSOS
# (simula lo que devolverá el PixelAnalyzer)
# --------------------------------------------------

def get_mock_noisy_pixels():
    """
    Simulación simple de píxeles ruidosos.
    Sustituir por Awkward Array real cuando esté listo.
    """
    return [
        (10, 20),
        (15, 25),
        (100, 300),
        (191, 399),   # borde válido
        # (192, 0),   # prueba fuera de rango (descomentar si quieres testear errores)
    ]


# --------------------------------------------------
# TEST PRINCIPAL
# --------------------------------------------------

def main():
    logger.info("Starting TxtManager test")

    # 1️⃣ Crear manager
    txt = TxtManager(base_dir=BASE_DIR, chip_id=CHIP_ID)

    # 2️⃣ Cargar fichero
    txt.load()

    # 3️⃣ Obtener píxeles ruidosos (mock)
    noisy_pixels = get_mock_noisy_pixels()
    logger.info("Noisy pixels: %s", noisy_pixels)

    # 4️⃣ Enmascarar píxeles
    txt.mask_noisy_pixels(noisy_pixels)

    # --------------------------------------------------
    # 5️⃣ TEST SAVE: TIMESTAMP (DEFAULT)
    # --------------------------------------------------
    logger.info("Testing save with TIMESTAMP mode (default)")
    path_timestamp = txt.save()
    logger.info("Saved with timestamp to: %s", path_timestamp)

    # --------------------------------------------------
    # 6️⃣ TEST SAVE: EXPLICIT NAME
    # --------------------------------------------------
    logger.info("Testing save with EXPLICIT name")
    explicit_name = "CMSIT_RD53A_F7_masked_TEST.txt"

    path_explicit = txt.save(
        mode=SaveMode.NEWFILE,
        output_path=explicit_name
    )
    logger.info("Saved with explicit name to: %s", path_explicit)

    # --------------------------------------------------
    # 7️⃣ TEST SAVE: OVERWRITE (⚠️ PELIGROSO)
    # --------------------------------------------------
    # ⚠️ Descomentar SOLO si estás seguro
    #
    # logger.warning("Testing OVERWRITE mode (this will overwrite the original file!)")
    # txt.save(mode=SaveMode.OVERWRITE)

    logger.info("TxtManager test completed successfully")


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()
