# MODULE IMPORTS
import pandas as pd
import sqlite3
import numpy as np
import matplotlib
import json
import gensim
import re
import twitter_credentials
import pickle
import keras
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy import API
from tweepy import Cursor
from bs4 import BeautifulSoup
from nltk.tokenize import WordPunctTokenizer
from nltk.corpus import stopwords
from nltk.stem.wordnet import WordNetLemmatizer
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.model_selection import train_test_split
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.models import Sequential
from keras.layers import Dense, Embedding, LSTM, Dropout
from keras.utils.np_utils import to_categorical
from keras.callbacks import ReduceLROnPlateau, EarlyStopping
from keras.models import load_model
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

class TwitterClient():

    # default argument for twitter_user (None) will default to myself
    def __init__(self, twitter_user=None):
        self.auth = TwitterAuthenticator().authenticate_twitter_app()
        self.twitter_client = API(self.auth)
        self.twitter_user = twitter_user

    def get_twitter_client_api(self):
        return self.twitter_client

    def get_user_timeline_tweets(self, num_tweets):
        tweets = []
        # gets num_tweets number of tweets from the timeline of the user stated 
        for tweet in Cursor(self.twitter_client.user_timeline, id = self.twitter_user).items(num_tweets):
            tweets.append(tweet)
        return tweets

    def get_friend_list(self, num_friends):
        friends = []
        for friend in Cursor(self.twitter_client.friends, id = self.twitter_user).items(num_friends):
            friends.append(friend)
        return friends

    def get_home_timeline_tweets(self, num_tweets):
        tweets = []
        for tweet in Cursor(self.twitter_client.home_timeline, id = self.twitter_user).items(num_tweets):
            tweets.append(tweet)
        return tweets

# this class is used for authenticating the Twitter application whenever needed
class TwitterAuthenticator():

    def authenticate_twitter_app(self):
        auth = OAuthHandler(twitter_credentials.CONSUMER_KEY, twitter_credentials.CONSUMER_SECRET)
        auth.set_access_token(twitter_credentials.ACCESS_TOKEN, twitter_credentials.ACCESS_TOKEN_SECRET)
        return auth

# this class is used for streaming and processing live tweets
class TwitterStreamer():

    def __init__(self):
        self.twitter_authenticator = TwitterAuthenticator()

    def stream_tweets(self):
        listener = TwitterListener()
        auth = self.twitter_authenticator.authenticate_twitter_app()
        stream = Stream(auth, listener)
        location_houston = [-95.866166, 29.532209, -95.088398, 30.182501]
        stream.filter(locations = location_houston) # filter the stream by location

# this class inherits from the StreamListener class and writes the received tweets to a file / catches any errors
class TwitterListener(StreamListener):
    def __init__(self):
        if not firebase_admin._apps:
          cred = credentials.Certificate('./houston-happiness-index-firebase-adminsdk-h4h8z-91ca39a417.json')
          firebase_admin.initialize_app(cred, {
          'databaseURL' : 'https://houston-happiness-index.firebaseio.com/'
          })
        firebase_admin.get_app()
    
    def on_data(self, data):
        try:
            json_load = json.loads(data)
            text = json_load['text']
            print(text)
            if (text.find("quarantine") > -1 or text.find("coronavirus") > -1 or text.find("covid") > -1 or text.find("online classes") > -1 or text.find("work from home") > -1 or text.find("lockdown") > -1):
                tweet_cleaner = TweetCleaner()
                modelObject = Model()
                text = tweet_cleaner.clean_tweet(text)
                score = modelObject.predict(text)
            
                root = db.reference('/')
                root.child('info').push().set({
                    'Tweet': str(text),
                    'Score': str(score)
                })
            return True
        except BaseException as error:
            print("Error on_data: %s", str(error))
        return True

    def on_error(self, status):
        if status == 420:
            return False # stop streaming tweets/data
    
# class that analyzes and categorizes the content from tweets
class TweetAnalyzer():
    
    def tweets_to_data_frame(self, tweets):
        df = pd.DataFrame(data = [tweet.text for tweet in tweets], columns = ['tweets'])
        df['id'] = np.array([tweet.id for tweet in tweets])
        df['len'] = np.array([len(tweet.text) for tweet in tweets])
        df['date'] = np.array([tweet.created_at for tweet in tweets])
        df['likes'] = np.array([tweet.favorite_count for tweet in tweets])
        df['retweets'] = np.array([tweet.retweet_count for tweet in tweets])
        return df

# class that retrieves .csv file of all the original tweets, cleans the tweets and stores them in a new .csv file
class TweetCleaner():
    
    def clean_all_tweets(self):
        data = pd.read_csv('./tweets.csv', encoding='latin-1') # enter your file location
        data.columns=["sentiment", "id", "date", "query", "user", "text"]
        data['sentiment'] = data['sentiment'].map({4:1, 0:0}) # converting 4 to 1
        
        df = data
        print ("Cleaning and parsing the tweets...\n")
        clean_tweet_texts = []

        end_range = df['text'].size - 1
        for i in range(0, end_range):
            if( (i+1) % 1000 == 0 ):
                print("Tweets " + str(i + 1) + " of " + str(1600000) + " has been processed")                                                                    
            clean_tweet_texts.append(self.clean_tweet(df['text'][i]))

        # creates dataframe with text and sentiment of each "cleaned" tweet
        clean_df = pd.DataFrame(clean_tweet_texts,columns=['text'])
        clean_df['target'] = df.sentiment

        # puts the information from the dataframe into a .csv file
        clean_df.to_csv('clean_tweet.csv',encoding='utf-8')

    def clean_tweet(self, text):
        negations_dic = {"isn't":"is not", "aren't":"are not", "wasn't":"was not", "weren't":"were not",
                "haven't":"have not","hasn't":"has not","hadn't":"had not","won't":"will not",
                "wouldn't":"would not", "don't":"do not", "doesn't":"does not","didn't":"did not",
                "can't":"can not","couldn't":"could not","shouldn't":"should not","mightn't":"might not",
                "mustn't":"must not"}

        neg_pattern = re.compile(r'\b(' + '|'.join(negations_dic.keys()) + r')\b')
        tok = WordPunctTokenizer()
        stop_words = set(stopwords.words('english')) 
        lem = WordNetLemmatizer()

        # HTML decoding (removing &amp; &quot; etc.)
        soupObject = BeautifulSoup(text, 'lxml')
        decodedText = soupObject.get_text()
        # removing the @ mention
        decodedText = re.sub(r'@[A-Za-z0-9_]+', '', decodedText)
        # removing website URL links 
        decodedText = re.sub(r'https?://[^ ]+', '', decodedText)
        decodedText = re.sub(r'www.[^ ]+', '', decodedText)
        # removing UTF-8 BOM byte sequences
        try: 
            decodedText = decodedText.decode("utf-8-sig").replace(u"\ufffd", "?")
        except:
            decodedText = decodedText
        # handle negatives (can't, don't etc.)
        decodedText = neg_pattern.sub(lambda x: negations_dic[x.group()], decodedText)
        # removes any non-letters (such as # in hashtags or numbers)
        decodedText = re.sub('[^A-Za-z]', " ", decodedText)
        # make all the letters lower-case
        decodedText = decodedText.lower()
        # tokenization to remove the unnecessary white space between words
        words = [x for x in tok.tokenize(decodedText) if len(x) > 1]
        # normalizing the words
        new_words = []
        for word in words:
            word_text = lem.lemmatize(word, 'v')
            new_words.append(word_text)
        # remove stop words
        decodedText = ' '.join(new_words)
        words = [word for word in decodedText.split() if word not in stop_words]
        finalString = ' '.join(words).strip()
        if finalString[0:2] == "rt":
            finalString = finalString[2:]
        return finalString

class CreateModel():

    def create_model(self):
        csv = 'clean_tweet.csv'
        df = pd.read_csv(csv,index_col=0)
        # drops the null tweets
        df.dropna(inplace=True)
        df.reset_index(drop=True,inplace=True)

        X = df.iloc[:,[0]]
        Y = df.iloc[:,1]

        X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=42)
        
        documents = [text.split() for text in X_train.text]
        w2v_model = gensim.models.Word2Vec(size = 300, window = 7, min_count = 10, workers = 8)
        w2v_model.build_vocab(documents)
        words = w2v_model.wv.vocab.keys()

        w2v_model.train(documents, total_examples = len(documents), epochs = 3)
        print(w2v_model.most_similar("hate"))

        tokenizer = Tokenizer()
        tokenizer.fit_on_texts(X_train.text)
        word_index = tokenizer.word_index
        vocab_size = len(word_index)
        X_train_padded = tokenizer.texts_to_sequences(X_train.text)
        X_train_padded = pad_sequences(X_train_padded, maxlen = 300)

        with open('tokenizer.pickle', 'wb') as handle:
            pickle.dump(tokenizer, handle, protocol = pickle.HIGHEST_PROTOCOL)

        embedding_matrix = np.zeros((vocab_size+1, 300))
        for word, i in tokenizer.word_index.items():
            if word in w2v_model.wv:
                embedding_matrix[i] = w2v_model.wv[word]

        model = Sequential()
        model.add(Embedding(vocab_size + 1, 300, weights = [embedding_matrix], input_length = 300, trainable = False))
        model.add(Dropout(0.5))
        model.add(LSTM(100, dropout = 0.2, recurrent_dropout = 0.2))
        model.add(Dense(1, activation = "sigmoid"))

        model.compile(loss='binary_crossentropy',
                    optimizer="adam",
                    metrics=['accuracy'])

        callbacks = [ ReduceLROnPlateau(monitor='val_loss', patience=5, cooldown=0),
                    EarlyStopping(monitor='val_acc', min_delta=1e-4, patience=5)]
        
        history = model.fit(X_train_padded, y_train,
                        batch_size=1024,
                        epochs=5,
                        validation_split=0.1,
                        verbose=1,
                        callbacks=callbacks)

        model.save('sentiment_analysis_model.h5')

class Model():

    def __init__(self):
        model = load_model('sentiment_analysis_model.h5')
        self.model = model

    def get_model(self):
        return model

    def get_tokenizer(self):
        csv = 'clean_tweet.csv'
        df = pd.read_csv(csv,index_col=0)
        # drops the null tweets
        df.dropna(inplace=True)
        df.reset_index(drop=True,inplace=True)

        X = df.iloc[:,[0]]
        Y = df.iloc[:,1]

        X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

        tokenizer = Tokenizer()
        tokenizer.fit_on_texts(X_train.text)
        return tokenizer

    def predict(self, text, include_neutral = True):
        tokenizer = self.get_tokenizer()
        x_test = pad_sequences(tokenizer.texts_to_sequences([text]), maxlen = 300)
        score = self.model.predict([x_test])[0]
        return score[0]
                
        
if __name__ == "__main__":

    # twitter_client = TwitterClient()
    # api = twitter_client.get_twitter_client_api()

    # tweet_analyzer = TweetAnalyzer()

    streamer = TwitterStreamer()

    streamer.stream_tweets()
    
    # tweets = api.user_timeline(screen_name = "realDonaldTrump", count = 60)




