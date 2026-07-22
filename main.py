"""Application entry point."""
import logging
from database import Database
from config import load_config
from ui.main_window import MainWindow
def main():
 logging.basicConfig(filename="radio_logbook.log",level=logging.DEBUG,format="%(asctime)s %(levelname)s %(name)s: %(message)s")
 app=MainWindow(Database(),load_config());app.mainloop()
if __name__ == "__main__":main()
