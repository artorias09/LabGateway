#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

#ifndef LABGATEWAY_URL
#define LABGATEWAY_URL "https://SEU-ENDERECO-LABGATEWAY"
#endif

#ifndef LABGATEWAY_TOKEN
#define LABGATEWAY_TOKEN "TOKEN_FORNECIDO_PELO_PROFESSOR"
#endif

#ifndef LABGATEWAY_INTERVALO_MS
#define LABGATEWAY_INTERVALO_MS 30000UL
#endif

class LabGatewayClass {
  String endpoint;
  String token;
  String station;
  unsigned long ultimoEnvio = 0;
  bool primeiroEnvio = true;

  static String escapeJson(const String &s) {
    String out;
    out.reserve(s.length() + 8);
    for (size_t i = 0; i < s.length(); i++) {
      char c = s[i];
      if (c == '"' || c == '\\') out += '\\';
      out += c;
    }
    return out;
  }

  static String numberJson(float value) { return String(value, 6); }
  static String numberJson(double value) { return String(value, 6); }

  template <typename T>
  static String numberJson(T value) { return String(value); }

  static void appendValues(String &, int &) {}

  template <typename T, typename... Rest>
  static void appendValues(String &json, int &index, T value, Rest... rest) {
    index++;
    if (index > 1) json += ",";
    json += "\"variavel_" + String(index) + "\":";
    json += numberJson(value);
    appendValues(json, index, rest...);
  }

  bool sendJson(const String &dataJson) {
    if (WiFi.status() != WL_CONNECTED) return false;

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    if (!http.begin(client, endpoint)) return false;

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-LabGateway-Token", token);

    String body = "{\"station\":\"" + escapeJson(station) +
                  "\",\"name\":\"" + escapeJson(station) +
                  "\",\"group\":\"\",\"data\":" + dataJson +
                  ",\"units\":{}}";

    int code = http.POST(body);
    http.end();
    return code >= 200 && code < 300;
  }

public:
  LabGatewayClass() : endpoint(LABGATEWAY_URL), token(LABGATEWAY_TOKEN) {
    if (endpoint.endsWith("/")) endpoint.remove(endpoint.length() - 1);
    endpoint += "/api/v1/measurements";

    uint64_t chip = ESP.getEfuseMac();
    char id[24];
    snprintf(id, sizeof(id), "esp32_%04X%08X",
             (uint16_t)(chip >> 32), (uint32_t)chip);
    station = String(id);
  }

  template <typename... Values>
  bool enviar(Values... values) {
    unsigned long agora = millis();

    if (!primeiroEnvio && (unsigned long)(agora - ultimoEnvio) < LABGATEWAY_INTERVALO_MS) {
      return true;
    }

    String data = "{";
    int index = 0;
    appendValues(data, index, values...);
    data += "}";

    bool ok = sendJson(data);
    if (ok) {
      ultimoEnvio = agora;
      primeiroEnvio = false;
    }
    return ok;
  }
};

inline LabGatewayClass LabGateway;
