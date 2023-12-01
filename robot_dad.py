import os, json, threading, time
import pvporcupine, pvcheetah
from pvrecorder import PvRecorder
from elevenlabs import voices, generate, play, stream
from openai import OpenAI
from elevenlabs import set_api_key

porcupine_key = os.environ.get("PORCUPINE_API_KEY")
openai_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")

client = OpenAI(api_key=openai_key)

ENDPOINT_DURATION_SECONDS = 2 # 'Quiet' seconds indicating the end of audio capture
VOICE = 'uQOBk31GP0vQaD1DiLi0' # Via Eleven Labs
AUDIO_DEVICE_NAME = 'MacBook Pro Microphone'
AUDIO_DEVICE = PvRecorder.get_available_devices().index(AUDIO_DEVICE_NAME)
OPENAI_MODEL = 'gpt-3.5-turbo-1106'

BASE_PROMPT = """You are Robot Dad, and will be speaking with one of my children,
trying to be a helpful parent. You explain things at a level appropriate for
an eight-year-old.

You are encouraging and helpful, but won't tolerate any inappropriate requests
or attempts at pranks or jokes. If you are asked or told anything
inappropriate, you gently say "nice try - but Robot Dad isn't falling for that!"

If you don't know how to reply, simply say "I'm just Robot Dad, not proper dad -
so I'm afraid I can't help you with that".

You usually answer in no more than 4 sentences - kids do not have long attention
spans - but you can provide longer answers if it's clearly needed.
"""

PREV_CTX_PROMPT = """

The last request and response you received is below. The next request may or may
not be a continuation of this conversation.

Previous request:
%s

Previous response:
%s
"""

PREV_CTX_TIMEOUT = 60 # seconds

keyword_paths=['Robot-Dad.ppn']
print(pvporcupine.KEYWORDS)



set_api_key(elevenlabs_key)

porcupine = pvporcupine.create(
    access_key=porcupine_key,
    keyword_paths=keyword_paths)

cheetah = pvcheetah.create(
    access_key=porcupine_key,
    endpoint_duration_sec=ENDPOINT_DURATION_SECONDS,
    enable_automatic_punctuation=True)

recorder = PvRecorder(
    frame_length=porcupine.frame_length,
    device_index=AUDIO_DEVICE)


break_audio = generate(text="Hmmmm...", voice=VOICE)
alert_audio = generate(text="What's up?", voice=VOICE)

def llm_req(prompt, txt):
    messages= [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f'Here is what the child has said: {txt}'}
    ]

    resp = client.chat.completions.create(model=OPENAI_MODEL,
    messages=messages)
    return resp.choices[0].message.content


# Speech-to-text using Picovoice's Cheetah
def capture_input():
    transcript = ''
    while True:
        partial_transcript, is_endpoint = cheetah.process(recorder.read())
        transcript += partial_transcript
        if is_endpoint:
            transcript += cheetah.flush()
            break
    return transcript.replace("What's up", "")


def play_async(audio):
    audio_thread = threading.Thread(target=play, args=(audio,))
    audio_thread.start()


def main():
    print('Listening...')

    recorder.start()

    prev_request = ''
    prev_response = ''
    last_wake_time = None

    try:
        while True:
            

            pcm = recorder.read()
            result = porcupine.process(pcm)

            if result >= 0:
                print('Detected Robot Dad')
                play_async(alert_audio)
                

                prompt = BASE_PROMPT
                current_time = time.time()
                if last_wake_time and current_time - last_wake_time < PREV_CTX_TIMEOUT:
                    prompt += PREV_CTX_PROMPT % (prev_request, prev_response)
                last_wake_time = current_time

                transcript = capture_input()
                print('Heard request: %s' % transcript)
                prev_request = transcript

                play_async(break_audio)

                resp = llm_req(prompt, transcript)
                print('Answering: %s' % resp)
                prev_response = resp

                resp_audio = generate(text=resp, voice=VOICE, stream=True)
                stream(resp_audio)
    except KeyboardInterrupt:
        pass

    recorder.stop()
    print('Stopped.')
main()
