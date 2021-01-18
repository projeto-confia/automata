import tweepy
import confia.monitor.authconfig as cfg
import confia.monitor.data_access as data
import abc
import time


class StreamInterface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'collect_data') and 
                callable(subclass.collect_data) and 
                hasattr(subclass, 'process_data') and 
                callable(subclass.process_data) and
                hasattr(subclass, 'persist_data') and 
                callable(subclass.persist_data) or 
                NotImplemented)

    @abc.abstractmethod
    def collect_data(self, interval: int):
        """
        Coleta dados da rede social.

        Parâmetros:
            interval (int) - Tempo em segundos para a coleta de dados.

        Retorna:
            TRUE se não ocorrer falha, FALSE caso contrário.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def process_data(self):
        """
        Processa os dados coletados da rede social.
        
        Retorna:
            True se não ocorrer falha, False caso contrário.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def persist_data(self):
        """
        Persiste os dados processados na base relacional.
        
        Retorna:
            True se não ocorrer falha, False caso contrário.
        """
        raise NotImplementedError


class TwitterStreamListener(tweepy.StreamListener):

    def on_connect(self):
        self.users = data.User()

    def on_status(self, status):
        """
        status: tweepy.models.status - objeto twitter
        """
        text = ''
        if hasattr(status, "retweeted_status"):  # Checa se é retweet
            try:
                text = status.retweeted_status.extended_tweet["full_text"]
            except AttributeError:
                text = status.retweeted_status.text
        else:
            try:
                text = status.extended_tweet["full_text"]
            except AttributeError:
                text = status.text

        print("\tID: {0} - @{1} - {2}\n".format(status.author.id, status.author.screen_name, text))
        self.users.write_in_csv(text, status.author.id)
        

class TwitterStream(StreamInterface):
    def __init__(self):
        self.streamListener = TwitterStreamListener()

    def collect_data(self, interval):
        """
        docstring
        """
        tokens = cfg.tokens
        auth = tweepy.OAuthHandler(tokens["consumer_key"], tokens["consumer_secret"])
        auth.set_access_token(tokens["access_token"], tokens["access_token_secret"])

        api = tweepy.API(auth)
        streamAccess = tweepy.Stream(auth=api.auth, listener=self.streamListener, tweet_mode='extended')
        print('vai iniciar o streaming')
        streamAccess.filter(track=["COVID", "covid", "Covid",  "coronavirus", "coronavírus", "covid-19", "vacina"], 
                            languages=["pt"],
                            is_async=True)
        time.sleep(interval)
        streamAccess.disconnect()

    def process_data(self):
        """
        docstring
        """
        pass

    def persist_data(self):
        """
        docstring
        """
        pass