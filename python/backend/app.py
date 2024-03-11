import json
import os
import mimetypes
import falcon
from falcon_multipart.middleware import MultipartMiddleware
from moviepy.editor import *
from AudioAnalyzer import AudioAnalyzer

STORAGE_PATH = "storage/"
smallModelPath = "models/vosk-model-small-en-us-0.15"
BIG_MODEL_PATH = "models/vosk-model-en-us-0.22"

esModelPath = "models/vosk-model-small-es-0.42"
frModelPath = "models/vosk-model-small-fr-0.22"
ruModelPath = "models/vosk-model-small-ru-0.22"
deModelPath = "models/vosk-model-small-de-0.15"


class Source(object):
    """
    Falcon resource for receiving audio/video and processing into json list of words

    Args:
        sessionKey - Unix timestamp from client. Used to name folder for files
        isVideo - boolean string
        Response - json list of words
        
    """
    def on_put(self, req, resp):
        sessionKey = req.get_param("key")

        isVideo = (req.get_param("isVideo") == "true")

        useBigModel = (req.get_param("useBigModel") == "true")

        fileObj = req.get_param("file")
        raw = fileObj.file.read()

        lang = req.get_param("lang")

        path = STORAGE_PATH + sessionKey
        wordsJson = ""
        
        os.makedirs(path, exist_ok=True)

        if isVideo:
            # save video
            with open((path + "/video.mp4"), "wb") as f:
                f.write(raw)
            fullClip = VideoFileClip((path + "/video.mp4"))
            fullClip.audio.write_audiofile(
                (path + "/audio.wav"), ffmpeg_params=["-ac", "1"], codec="pcm_s16le"
            )
        else:
            # save audio
            with open((path + "/audio.wav"), "wb") as f:
                f.write(raw)
            
        wordsJson = processAudio(sessionKey, useBigModel, lang)

        resp.text = json.dumps({"wordsJson": wordsJson})
        resp.status = falcon.HTTP_200



# Falcon resource for generating audio/video output
# sessionKey - Unix timestamp from client. Used to name folder for files
# isVideo - boolean string
# audioOnly - boolean string, true for audio, true or false for video
# chosenWords - json list of word objects: {"id" : String, "end" : String, "word" : String}
# "id" alias for start time
# Response - wav audio or mp4 video
class Generate(object):
    def on_put(self, req, resp):
        mediaObj = req.get_media()
        sessionKey = mediaObj.get("sessionKey")
        chosenWords = mediaObj.get("chosenWords")
        isVideo = mediaObj.get("isVideo")
        audioOnly = mediaObj.get("audioOnly")

        path = ""
        if isVideo and not audioOnly:
            path = STORAGE_PATH + str(sessionKey) + "/concat.mp4"
            generate_video(sessionKey, chosenWords)
        else:
            path = STORAGE_PATH + str(sessionKey) + "/concat.wav"
            generate_audio(sessionKey, chosenWords)

        generatedFile = open(path, "rb")
        content_length = os.path.getsize(path)

        resp.content_type = mimetypes.guess_type(path)[0]
        resp.stream = generatedFile
        resp.content_length = content_length
        resp.status = falcon.HTTP_200


# Takes audio file and returns json list of word objects
def processAudio(sessionKey, useBigModel, lang):
    audioFile = STORAGE_PATH + str(sessionKey) + "/audio.wav"

    modelPath = ""
    if lang == "en":
        modelPath = BIG_MODEL_PATH if useBigModel else smallModelPath
    elif lang == "es":
        modelPath = esModelPath
    elif lang == "fr":
        modelPath = frModelPath
    elif lang == "ru":
        modelPath = ruModelPath
    elif lang == "de":
        modelPath = deModelPath

    audioAnalyzer = AudioAnalyzer(modelPath, audioFile)
    audioAnalyzer.analyze()
    return audioAnalyzer.getWordsJson()


def generate_video(sessionKey, wordsJson):
    """ Takes json word objects and appends sublcips into video """
    words = json.loads(wordsJson)
    _clip = VideoFileClip(STORAGE_PATH + str(sessionKey) + "/video.mp4")

    subclips = [_clip.subclip(float(word["id"]), float(word["end"])) for word in words]
    concatClip = concatenate_videoclips(subclips)
    concatClip.write_videofile(STORAGE_PATH + str(sessionKey) + "/concat.mp4")


def generate_audio(sessionKey, wordsJson):
    """ Takes json word objects and appends sublcips into audio """
    words = json.loads(wordsJson)
    subclips = []
    fullAudioClip = AudioFileClip(STORAGE_PATH + str(sessionKey) + "/audio.wav")

    for i in range(len(words)):
        subclips.append(
            fullAudioClip.subclip(float(words[i]["id"]), float(words[i]["end"]))
        )

    concatClip = concatenate_audioclips(subclips)
    concatClip.write_audiofile(
        STORAGE_PATH + str(sessionKey) + "/concat.wav", codec="pcm_s16le"
    )


# Falcon app
app = application = falcon.App(
    middleware=[
        falcon.CORSMiddleware(allow_origins="*", allow_credentials="*"),
        MultipartMiddleware(),
    ]
)
app.add_route("/source", Source())
app.add_route("/generate", Generate())
