log of installing locallama


**Install llama.cpp on Raspberry Pi 5**

1. Update
   `sudo apt update && sudo apt upgrade -y`
   `sudo apt install libcurl4-openssl-dev -y`

2. Install deps
   `sudo apt install build-essential cmake git -y`

3. Clone
   `git clone llama-cpp repo && cd llama-cpp`
   *(replace with ref id if web used — omitted as static)*

4. Build
   `cmake -B build -DLLAMA_NATIVE=OFF -DLLAMA_BUILD_TESTS=OFF`
   `cmake --build build --config Release -j4`

5. Get quantized model (GGUF, 1B–3B recommended)
   *(download separately on your device)*

6. Run
   `./build/bin/llama-cli -m model.gguf -p "hi" -n 256`

7. (Optional) Enable server API
   `./build/bin/llama-server -m model.gguf --host 0.0.0.0 --port 8080`

---

Ensure `v1/chat/completions` works:

1. Install deps
   `sudo apt install libcurl4-openssl-dev nlohmann-json3-dev -y`

2. Reconfigure with v1 API ON
   `cmake -B build -DLLAMA_CURL=OFF -DLLAMA_NATIVE=OFF -DLLAMA_SERVER_OPENAI=ON`

3. Build
   `cmake --build build -j4`

4. Run server
   `./build/bin/llama-server -m ~/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf --port 8080`

5. Test endpoint

```
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-3.2-tiny","messages":[{"role":"user","content":"Hi"}],"temperature":0.3}'
```

If JSON reply returns → ready.


