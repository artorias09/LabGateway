#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <math.h>

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
  unsigned long ultimaTentativa = 0;
  bool primeiraTentativa = true;

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

  static void appendValues(String &, int &, bool &) {}

  template <typename T, typename... Rest>
  static void appendValues(String &json, int &index, bool &valid, T value, Rest... rest) {
    double numeric = static_cast<double>(value);
    if (!isfinite(numeric)) {
      valid = false;
      return;
    }

    index++;
    if (index > 1) json += ",";
    json += "\"variavel_" + String(index) + "\":";
    json += numberJson(value);
    appendValues(json, index, valid, rest...);
  }

  void ensureStation() {
    if (station.length()) return;

    uint64_t chip = ESP.getEfuseMac();
    char id[24];
    snprintf(id, sizeof(id), "esp32_%04X%08X",
             (uint16_t)(chip >> 32), (uint32_t)chip);
    station = String(id);
  }

  bool sendJson(const String &dataJson) {
    if (WiFi.status() != WL_CONNECTED) return false;

    ensureStation();

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
  }

  template <typename... Values>
  bool enviar(Values... values) {
    unsigned long agora = millis();

    if (!primeiraTentativa &&
        (unsigned long)(agora - ultimaTentativa) < LABGATEWAY_INTERVALO_MS) {
      return true;
    }

    primeiraTentativa = false;
    ultimaTentativa = agora;

    String data = "{";
    int index = 0;
    bool valid = true;
    appendValues(data, index, valid, values...);
    data += "}";

    if (!valid || index == 0) return false;
    return sendJson(data);
  }
};

inline LabGatewayClass LabGateway;
