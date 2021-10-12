import pandas as pd
import csv, os
import math
from datetime import datetime
from src.orm.db_wrapper import DatabaseWrapper

class DAO:

    def __init__(self):
        self._db = DatabaseWrapper()
    
    def update_news_labels(self, id_news, classification_outcome, ground_truth_label, prob_label):
        """
        Atualiza os atributos 'classification_outcome', 'prob_classification' e 'ground_truth_label' referentes à notícia 'id_news'.
        """
        args = (classification_outcome, ground_truth_label, prob_label, id_news)
        
        self._db.execute("UPDATE detectenv.news SET classification_outcome = %s, ground_truth_label = %s, prob_classification = %s \
            WHERE id_news = %s", args)
        
        self._db.commit()

    # TODO: testar funcionalidade no painel administrativo.
    def get_top_users_which_shared_news_ics(self, num_users):
        """
        Recupera os top usuários com maiores taxas de compartilhamento de notícias fake e not fake.

        Args:
            num_users (int): o número máximo de usuários para serem retornados.
        """
        query = f"with tabela as ( \
		(select * from \
			(select detectenv.social_media_account.id_account_social_media, detectenv.social_media_account.screen_name, \
			count(detectenv.news.classification_outcome) as total_news, \
			count(detectenv.news.classification_outcome) filter (where detectenv.news.classification_outcome = true) as total_fake_news, \
			count(detectenv.news.classification_outcome) filter (where detectenv.news.classification_outcome = false) as total_not_fake_news \
			from detectenv.post \
			inner join detectenv.social_media_account \
				on detectenv.post.id_social_media_account = detectenv.social_media_account.id_social_media_account \
			inner join detectenv.news \
				on detectenv.post.id_news = detectenv.news.id_news \
			group by \
				detectenv.social_media_account.id_account_social_media, detectenv.social_media_account.screen_name) tbl \
			where tbl.total_news > 0) \
            limit = {num_users}) \
		select *, ((tabela.total_fake_news::decimal) / (tabela.total_news::decimal)) as rate_fake_news, ((tabela.total_not_fake_news::decimal) / (tabela.total_news::decimal)) as rate_not_fake_news \
		from tabela;"

        return self.query_to_dataframe(query)

    def get_unlabeled_news_shared_by_reputed_users(self):
        """
        Recupera as notícias sem rótulos compartilhadas por contas de usuários reputados.
        """

        query = "SELECT q.id_social_media_account, q.probalphan, q.probbetan, q.probumalphan, q.probumbetan, post.id_post, news.id_news, \
                news.classification_outcome, news.ground_truth_label, news.prob_classification \
                FROM \
                (SELECT * FROM detectenv.social_media_account AS sma WHERE \
                        (sma.probalphan != 0.5 OR sma.probbetan != 0.5 OR sma.probumalphan != 0.5 OR sma.probumbetan != 0.5) \
                ORDER BY id_social_media_account ASC) AS q, detectenv.news AS news, detectenv.post AS post \
                WHERE q.id_social_media_account = post.id_social_media_account AND post.id_news = news.id_news AND news.ground_truth_label IS NULL;"

        return self.query_to_dataframe(query)

    # TODO: separar este método em dois métodos distintos: um para inserir novos usuários e outro para atualizar usuários existentes. 
    # TODO: Utilizar, para isso, métodos da para inserção e atualização única da biblioteca 'psycopg2'.

    def update_social_media_accounts(self, list_social_media_accounts):
        
        self._db.execute_many_values("UPDATE detectenv.social_media_account SET \
            id_social_media = %s, \
            id_owner = %s \
            screen_name = %s \
            date_creation = %s \
            blue_badge = %s \
            probalphan = %s \
            probbetan = %s \
            probumalphan = %s \
            probumbetan = %s \
            id_account_social_media = %s \
            WHERE id_account_social_media = %s;", list_social_media_accounts)

        self._db.commit()

    def insert_update_user_accounts_db(self, users):
        """
        Insere uma nova conta de usuário ou, caso já exista, atualiza seus atributos a partir do atributo 'id_account_social_media'.

        Args:
            users (dataframe): dataframe contendo os usuários a serem inseridos/atualizados no banco de dados.

        Yields:
            str: mensagem de andamento da operação.
        """

        i = 1
        aux = -1
        total = len(users.index)

        for _, row in users.iterrows():
            progress = float((i / total) * 100)
            
            if aux != int(progress): 
                aux = int(progress)            
                
                if aux % 10 == 0 and aux > 0:
                    yield f"Progresso de inserção/atualização de contas de usuário: {aux}%"

            id_social_media             = 2 # TODO: mudar isso quando começarmos a trabalhar com outras redes sociais.
            id_owner                    = None if math.isnan(row["id_owner"]) else int(row["id_owner"])
            screen_name                 = str(row["screen_name"])
            date_creation               = row["date_creation"]
            blue_badge                  = row["blue_badge"]
            probAlphaN                  = row["probAlphaN"]
            probUmAlphaN                = row["probUmAlphaN"]
            probBetaN                   = row["probBetaN"]
            probUmBetaN                 = row["probUmBetaN"]
            id_account_social_media     = row["id_account_social_media"]

            command = f"INSERT INTO detectenv.social_media_account(id_social_media, id_owner, screen_name, date_creation, blue_badge, probalphan, probbetan, probumalphan, probumbetan, id_account_social_media) \
                VALUES ({id_social_media}, {id_owner}, {screen_name}, {date_creation}, {blue_badge}, {probAlphaN}, {probBetaN}, {probUmAlphaN}, {probUmBetaN}, {id_account_social_media}) \
                ON CONFLICT (id_account_social_media) DO \
		        UPDATE SET probalphan = {probAlphaN}, probbetan = {probBetaN}, probumalphan = {probUmAlphaN}, probumbetan = {probUmBetaN} \
                WHERE social_media_account.id_account_social_media = {id_account_social_media};"
            
            self._db.execute(command, ())
            self._db.commit()
            i = i + 1
        
        yield "Processo de inserção/atualização de contas de usuários concluído."


    def get_list_of_ids_press_media_accounts(self):
        """Retorna uma lista com os id's das contas de mídias sociais que representam veículos de imprensa.

        Returns:
            list: lista dos id's das contas de veículos de imprensa.
        """
        press_media_accounts = self.query_to_dataframe("SELECT tbl.id_social_media_account, tbl.id_owner FROM \
                                    (SELECT * FROM detectenv.social_media_account WHERE id_owner IS NOT NULL) tbl, detectenv.owner \
                                    WHERE tbl.id_owner = detectenv.owner.id_owner \
                                    AND detectenv.owner.is_media = true AND detectenv.owner.is_media_activated = true;")
                                    
        return list(press_media_accounts['id_social_media_account'])
    
    def get_users_which_shared_the_news(self, id_news, all_users=True):
        """
        Retorna as contas de usuários reputados que compartilharam a notícia, representada por 'id_news'.

        Args:
            id_news (int): o id da notícia.
            all_users (bool): se igual a 'False', retorna apenas os usuários reputados que compartilharam a notícia (menos os veículos de imprensa). 
            Se igual a 'True', retorna todos os usuários que compartilharam a notícia (menos os veículos de imprensa).

        Returns:
            dataframe: dataframe contendo os usuários que compartilharam a notícia.
        """
        return self.query_to_dataframe(f"SELECT * FROM detectenv.post p, detectenv.news n, detectenv.social_media_account sma WHERE \
            n.id_news = p.id_news AND p.id_social_media_account = sma.id_social_media_account AND \
            (sma.probalphan != 0.5 OR sma.probbetan != 0.5 OR sma.probumalphan != 0.5 OR sma.probumbetan != 0.5) AND \
            p.id_news = {id_news};") \
            if not all_users \
            else \
                self.query_to_dataframe(f"SELECT * FROM detectenv.post p, detectenv.news n, detectenv.social_media_account sma WHERE \
                n.id_news = p.id_news AND p.id_social_media_account = sma.id_social_media_account AND \
                (sma.probalphan IS NOT NULL AND sma.probbetan IS NOT NULL AND sma.probumalphan IS NOT NULL AND sma.probumbetan IS NOT NULL) \
                AND p.id_news = {id_news};")

    def get_labels_of_news_shared_by_user(self, id_social_media_account):
        """
        Retorna os rótulos das notícias compartilhadas pela conta de usuário, representado por 'id_social_media_account'.

        Args:
            id_social_media_account (int): o id da conta de usuário.

        Returns:
            Dataframe: um dataframe contendo todos as notícias compartilhadas pela conta de usuário.
        """

        query = f"SELECT n.id_news, n.ground_truth_label \
                FROM detectenv.post p, detectenv.news n, detectenv.social_media_account sma \
                WHERE n.id_news = p.id_news \
                AND p.id_social_media_account = sma.id_social_media_account \
                AND n.ground_truth_label IS NOT NULL \
                AND sma.id_social_media_account = {id_social_media_account};"

        return self.query_to_dataframe(query)

    def get_labeled_news(self):
        """
        Retorna as notícias rotuladas presentes no banco de dados.

        Returns:
            dataframe: o dataframe contendo todas as notícias rotuladas.
        """
        return self.query_to_dataframe("SELECT * FROM detectenv.news WHERE ground_truth_label IS NOT NULL;")
            
    def query_to_dataframe(self, query):
        """
        Executa uma query to tipo 'select' e retorna a consulta em formato Pandas Dataframe.

        Args:
            query (str): a consulta do tipo 'select' a ser executada no banco de dados.

        Returns:
            dataframe: o dataframe com o resultado da consulta no banco de dados.
        """
        return pd.read_sql_query(query, self._db.connection)