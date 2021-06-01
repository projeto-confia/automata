from src.fcmanager.fact_check_manager import FactCheckManager
import logging


class FactCheckManagerFacade(object):
    """
    docstring
    """

    def __init__(self):
        self._logger = logging.getLogger('automata')
        

    def run(self):
        try:
            self._logger.info('Running FactCheckManager...')
            fact_check_manager = FactCheckManager()
            fact_check_manager.process_agency_feed()
            fact_check_manager.persist_data()
            self._logger.info('FactCheckManager finished.')
        except:
            raise
