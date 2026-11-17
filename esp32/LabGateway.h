#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

class LabGatewayClient {
  String endpoint;
  String token;
  String station;
  String stationName;
  String groupName;

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

public:
  LabGatewayClient(const char *baseUrl, const char *apiToken,
                   const char *stationId, const char *name, const char *group)
      : token(apiToken), station(stationId), stationName(name), groupName(group) {
    endpoint = String(baseUrl);
    if (endpoint.endsWith("/")) endpoint.remove(endpoint.length() - 1);
    endpoint += "/api/v1/measurements";
  }

  bool send(const String &dataJson, const String &unitsJson = "{}") {
    if (WiFi.status() != WL_CONNECTED) return false;
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    if (!http.begin(client, endpoint)) return false;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-LabGateway-Token", token);
    String body = "{\"station\":\"" + escapeJson(station) +
      "\",\"name\":\"" + escapeJson(stationName) +
      "\",\"group\":\"" + escapeJson(groupName) +
      "\",\"data\":" + dataJson + ",\"units\":" + unitsJson + "}";
    int code = http.POST(body);
    http.end();
    return code >= 200 && code < 300;
  }
};
