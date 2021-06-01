from src.scraping.scraping import Scraping
import logging


class ScrapingFacade(object):
    """
    docstring
    """

    def __init__(self):
        self._logger = logging.getLogger('automata')


    def run(self):
        try:
            self._logger.info('Running Scraping...')
            scraping = Scraping()
            # TODO: refatorar
            # transferir o teste condicional para scraping.py
            if not scraping.initial_load:
                scraping.update_data()
            else:
                scraping.fetch_data()
            scraping.persist_data()
            self._logger.info('Scraping finished.')
        except:
            raise
