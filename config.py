import os

class Config():
    DEBUG = False
    TESTING = False
    CSRF_ENABLE = True
    SECTRET_KEY = "Secret"

class Development(Config):
    DEBUG = True
    TESTING = True

class Production(Config):
    DEBUG = False
    TESTING = False

class Testing(Config):
    DEBUG = True
    TESTING = True

app_config ={
    "development" : Development(),
    "testing" : Testing(),
    "production" : Production()
}
