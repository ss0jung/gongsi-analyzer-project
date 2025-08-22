package com.sjproject.gongsianalyzer.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

  private final String fastApiUrl;
  private final String dartApiUrl;

  public WebClientConfig(
      @Value("${external.api.fast.url}") String fastApiUrl,
      @Value("${external.api.dart.url}") String dartApiUrl) {
    this.fastApiUrl = fastApiUrl;
    this.dartApiUrl = dartApiUrl;
  }

  @Bean("fastApiWebClient")
  public WebClient fastApiWebClient() {
    return WebClient.builder()
        .baseUrl(fastApiUrl)
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .build();
  }

  @Bean("dartApiWebClient")
  public WebClient dartApiWebClient() {
    return WebClient.builder()
        .baseUrl(dartApiUrl)
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .build();
  }

  @Bean("fileDownloadWebClient")
  public WebClient fileDownloadWebClient() {
    final int bufferSize = 10 * 1024 * 1024; // 10MB

    ExchangeStrategies exchangeStrategies = ExchangeStrategies.builder()
        .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(bufferSize))
        .build();

    return WebClient.builder()
        .exchangeStrategies(exchangeStrategies)
        .build();
  }
}