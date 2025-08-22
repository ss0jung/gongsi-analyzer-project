package com.sjproject.gongsianalyzer.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono; // Mono를 임포트합니다.

import java.util.Map;

@Service
public class QueryService {

  private final WebClient webClient;

  @Autowired
  public QueryService(@Qualifier("fastApiWebClient")  WebClient webClient) {
    // 설정 클래스에서 생성한 WebClient 빈을 주입받습니다.
    this.webClient = webClient;
  }

  /**
   * Python RAG API를 호출하여 답변을 가져옵니다.
   * @param question 사용자의 질문
   * @return Mono<Map> 형태의 비동기 응답
   */
  public Mono<Map> getAnswerFromPython(String question) {

    // Python API의 요청 본문과 동일한 구조의 객체
    Map<String, String> requestBody = Map.of("question", question);

    // WebClient를 사용한 POST 요청
    return webClient.post()           // 1. HTTP POST 메서드 지정
        .uri("/query")            // 2. 상세 경로 지정 (baseUrl 뒤에 붙음)
        .bodyValue(requestBody)   // 3. 요청 본문(body)에 데이터 설정
        .retrieve()               // 4. 요청을 보내고 응답을 받음
        .bodyToMono(Map.class);   // 5. 응답 본문을 Mono<Map> 형태로 변환
  }
}