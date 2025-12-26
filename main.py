import sys
import os
from PySide6.QtWidgets import QApplication
from src.ui import MainWindow
from src.utils import setup_logger

def main():
    setup_logger()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()