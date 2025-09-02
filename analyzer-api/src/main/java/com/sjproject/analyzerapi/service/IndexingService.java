package com.sjproject.analyzerapi.service;

import java.nio.file.Path;
import java.util.Collections;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Slf4j
@Service
public class IndexingService {

  private final WebClient fastApiWebClient;

  public IndexingService(@Qualifier("fastApiWebClient") WebClient fastApiWebClient) {
    this.fastApiWebClient = fastApiWebClient;
  }

  /**
   * Python 인덱싱 FastAPI 서버에 HTTP 요청을 보내 인덱싱을 트리거합니다.
   *
   * @param dataFilePath 인덱싱할 데이터 파일(XML)의 경로
   */
  public void triggerIndexingApi(Path dataFilePath) {
    log.info("Start fast api call for indexing processing");
    log.info("전달 파일 경로: {} ", dataFilePath.toString());

    // Python의 IndexingRequest 모델에 맞게 {"file_path": "경로"} 형식의 JSON으로 만듦
    Map<String, String> requestBody = Collections.singletonMap("file_path", dataFilePath.toAbsolutePath().toString());

    try {
      // WebClient를 사용하여 POST 요청 전송 및 응답 받기
      String response = fastApiWebClient.post()
          .uri("/api/v1/documents/index") // Base URL은 WebClientConfig에 설정되어 있음
          .bodyValue(requestBody)
          .retrieve()
          .bodyToMono(String.class)
          .block();

      log.info("Success fast api call for indexing processing. response: {}", response);

    } catch (WebClientResponseException e) {
      // API 서버가 4xx, 5xx 에러를 반환한 경우
      log.error("Fail fast api call for indexing processing. statusCode: {}, response: {}", e.getStatusCode(), e.getResponseBodyAsString());
      throw new RuntimeException("Fail fast api call for indexing processing: " + e.getMessage());
    } catch (Exception e) {
      // 네트워크 오류 등 WebClient 호출 자체에서 예외 발생 시
      log.error("Cannot connect to fast API server. {}", e.getMessage());
      throw new RuntimeException("Cannot connect to fast API server.: " + e.getMessage());
    }
  }
}
