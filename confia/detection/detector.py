import csv 
import pandas as pd
import numpy as np
import math
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, accuracy_score
from confia.orm.db_wrapper import DatabaseWrapper

class Detector:

    def __init__(self, laplace_smoothing=0.01, omega=0.5):

        self.__db         =    DatabaseWrapper()
        self.__users      =    pd.read_sql_query("select * from detectenv.social_media_account;", self.__db.connection)
        self.__news       =    pd.read_sql_query("select * from detectenv.news;", self.__db.connection)
        self.__news_users =    pd.read_sql_query("select * from detectenv.post;", self.__db.connection)
        self.__smoothing  =    laplace_smoothing
        self.__omega      =    omega

    def train_ics(self, test_size = 0.3):
        """
        Etapa de treinamento: calcula os parâmetros de cada usuário a partir do Implict Crowd Signals.        
        """
        self.__init_params(test_size)
        
        for userId in self.__train_news_users["id_social_media_account"].unique():            
            
            # obtém os labels das notícias compartilhadas por cada usuário.
            newsSharedByUser = list(self.__train_news_users["ground_truth_label"].loc[self.__train_news_users["id_social_media_account"] == userId])
            
            # calcula a matriz de opinião para cada usuário.
            totR        = newsSharedByUser.count(0)
            totF        = newsSharedByUser.count(1)
            alphaN      = totR + self.__smoothing
            umAlphaN    = ((totF + self.__smoothing) / (self.__qtd_F + self.__smoothing)) * (self.__qtd_V + self.__smoothing)
            betaN       = (umAlphaN * (totR + self.__smoothing)) / (totF + self.__smoothing)
            umBetaN     = totF + self.__smoothing

            # calcula as probabilidades para cada usuário.
            probAlphaN      = alphaN / (alphaN + umAlphaN)
            probUmAlphaN    = 1 - probAlphaN
            probBetaN       = betaN / (betaN + umBetaN)
            probUmBetaN     = 1 - probBetaN
            self.__users.loc[self.__users["id_social_media_account"] == userId, "probAlphaN"]   = probAlphaN
            self.__users.loc[self.__users["id_social_media_account"] == userId, "probBetaN"]    = probBetaN
            self.__users.loc[self.__users["id_social_media_account"] == userId, "probUmAlphaN"] = probUmAlphaN
            self.__users.loc[self.__users["id_social_media_account"] == userId, "probUmBetaN"]  = probUmBetaN

        self.__test_ics()

        # salva os parâmetros dos usuários no banco de dados. 
        for _, row in self.__users.iterrows():
            id_account      = str(row["id_social_media_account"].astype(int))
            probAlphaN      = str(row["probAlphaN"])
            probUmAlphaN    = str(row["probUmAlphaN"])
            probBetaN       = str(row["probBetaN"])
            probUmBetaN     = str(row["probUmBetaN"])
            
            args = (id_account, 2, None, None, None, None, probAlphaN, probBetaN, probUmAlphaN, probUmBetaN)
            self.__db.execute("DO $$ BEGIN PERFORM insert_update_social_media_account(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s); END $$;", args)

    def __init_params(self, test_size = 0.3):

        # divide 'self.__news_users' em treino e teste.
        labels = self.__news["ground_truth_label"]
        self.__X_train_news, self.__X_test_news, _, _ = train_test_split(self.__news, labels, test_size=test_size, stratify=labels)

        # # armazena em 'self.__train_news_users' as notícias compartilhadas por cada usuário.
        self.__train_news_users = pd.merge(self.__X_train_news, self.__news_users, left_on="id_news", right_on="id_news")
        self.__test_news_users  = pd.merge(self.__X_test_news, self.__news_users, left_on="id_news", right_on="id_news")

        # conta a qtde de noticias verdadeiras e falsas presentes no conjunto de treino.
        self.__qtd_V = self.__news["ground_truth_label"].value_counts()[0]
        self.__qtd_F = self.__news["ground_truth_label"].value_counts()[1]

        # filtra apenas os usuários que não estão em ambos os conjuntos de treino e teste.
        self.__train_news_users = self.__train_news_users[self.__train_news_users["id_social_media_account"].isin(self.__test_news_users["id_social_media_account"])]

        # inicializa os parâmetros dos usuários.
        totR            = 0
        totF            = 0
        alphaN          = totR + self.__smoothing
        umAlphaN        = ((totF + self.__smoothing) / (self.__qtd_F + self.__smoothing)) * (self.__qtd_V + self.__smoothing)
        betaN           = (umAlphaN * (totR + self.__smoothing)) / (totF + self.__smoothing)
        umBetaN         = totF + self.__smoothing
        probAlphaN      = alphaN / (alphaN + umAlphaN)
        probUmAlphaN    = 1 - probAlphaN
        probBetaN       = betaN / (betaN + umBetaN)
        probUmBetaN     = 1 - probBetaN
        self.__users["probAlphaN"]    = probAlphaN
        self.__users["probUmAlphaN"]  = probUmAlphaN
        self.__users["probBetaN"]     = probBetaN
        self.__users["probUmBetaN"]   = probUmBetaN

    def __test_ics(self):
        """
        etapa de avaliação: avalia a notícia com base nos parâmetros de cada usuário obtidos na etapa de treinamento.
        """
        predicted_labels = []
        unique_id_news   = self.__test_news_users["id_news"].unique()

        for newsId in unique_id_news:
            # recupera os ids de usuário que compartilharam a notícia representada por 'newsId'.
            usersWhichSharedTheNews = list(self.__news_users["id_social_media_account"].loc[self.__news_users["id_news"] == newsId])

            productAlphaN    = 1.0
            productUmAlphaN  = 1.0
            productBetaN     = 1.0
            productUmBetaN   = 1.0
            
            for userId in usersWhichSharedTheNews:
                i = self.__users.loc[self.__users["id_social_media_account"] == userId].index[0]

                productAlphaN   = productAlphaN  * self.__users.at[i, "probAlphaN"]
                productUmBetaN  = productUmBetaN * self.__users.at[i, "probUmBetaN"]
            
            # inferência bayesiana
            reputation_news_tn = (self.__omega * productAlphaN * productUmAlphaN) * 100
            reputation_news_fn = ((1 - self.__omega) * productBetaN * productUmBetaN) * 100
            
            if reputation_news_tn >= reputation_news_fn:
                predicted_labels.append(0)
            else:
                predicted_labels.append(1)

        # mostra os resultados da matriz de confusão e acurácia.
        print(self.__users)
        print(confusion_matrix(self.__X_test_news["ground_truth_label"], predicted_labels))
        print(accuracy_score(self.__X_test_news["ground_truth_label"], predicted_labels))

    def insert_news(self):
        from datetime import datetime

        news = pd.read_csv("confia/data/news.csv", sep=";")
        news["ground_truth_label"] = [0 if newsId <= 300 else 1 for newsId in news["newsId"]]
        
        for _, row in news.iterrows():
            id_news     = int(row["newsId"])
            id_original = str(row["idOriginal"])
            text_news   = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
            date_time   = str(datetime.now())
            gt_label    = bool(row["ground_truth_label"])

            args = (id_news, text_news, date_time, None, gt_label, id_original)
            print(args)
            self.__db.execute("INSERT INTO detectenv.news (id_news, text_news, datetime_publication, classification_outcome, ground_truth_label, id_news_original) VALUES (%s, %s, %s, %s, %s, %s);", args)
            self.__db.commit()

    def insert_post(self):
        from datetime import datetime

        for _, row in self.__news_users.iterrows():
            id_social_media_account = int(row["id_social_media_account"])
            id_news                 = int(row["id_news"])
            text_post               = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
            date_time               = str(datetime.now())

            args = (id_social_media_account, id_news, None, text_post, 0, 0, date_time)
            self.__db.execute("INSERT INTO detectenv.post (id_social_media_account, id_news, parent_id_post, text_post, num_likes, num_shares, datetime_post) VALUES (%s, %s, %s, %s, %s, %s, %s);", args)

    def read_news_users_from_file(self, news_users_file="confia/data/news_users.csv"):
        self.__news_users = pd.read_csv(news_users_file, sep=';')