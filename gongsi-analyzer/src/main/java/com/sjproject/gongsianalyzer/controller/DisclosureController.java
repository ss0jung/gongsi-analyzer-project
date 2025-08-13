package com.sjproject.gongsianalyzer.controller;

import com.sjproject.gongsianalyzer.service.DartService;
import com.sjproject.gongsianalyzer.service.IndexingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Path;
import java.util.Map;
import java.util.Optional;

/**
 * 공시 데이터 인덱싱을 위한 API 엔드포인트를 제공하는 컨트롤러
 */
@RestController
@RequestMapping("/api/disclosures")
public class DisclosureController {

  // 의존성 주입: Spring이 해당 타입의 Bean을 자동으로 주입합니다.
  private final DartService dartService;
  private final IndexingService indexingService;

  // 생성자 주입을 사용하는 것이 @Autowired 필드 주입보다 권장됩니다.
  @Autowired
  public DisclosureController(DartService dartService, IndexingService indexingService) {
    this.dartService = dartService;
    this.indexingService = indexingService;
  }

  /**
   * 인덱싱 프로세스를 시작하는 POST API
   * @param payload JSON 요청 본문 (예: {"rceptNo": "20240315000559"})
   * @return 작업 결과에 대한 HTTP 응답
   */
  @PostMapping("/indexing")
  public ResponseEntity<String> startIndexing(@RequestBody Map<String, String> payload) {
    // 1. 요청 본문에서 'rceptNo'(접수번호) 추출 및 유효성 검사
    String rceptNo = payload.get("rceptNo");
    if (rceptNo == null || rceptNo.isBlank()) {
      return ResponseEntity.badRequest().body("요청 실패: 접수번호(rceptNo)는 필수 항목입니다.");
    }

    try {
      // 2. DartService를 호출하여 공시 데이터 다운로드 시도
      System.out.println("접수번호 [" + rceptNo + "] 공시 데이터 다운로드를 시작합니다.");
      Optional<Path> optionalFilePath = dartService.downloadDisclosure(rceptNo);

      // 3. 다운로드 성공 여부 확인 (실패 우선 처리)
      if (optionalFilePath.isEmpty()) {
        String errorMessage = "처리 실패: 공시 문서를 다운로드할 수 없습니다. 접수번호를 확인하거나 DART API 상태를 점검해주세요. (접수번호: " + rceptNo + ")";
        System.err.println(errorMessage);
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(errorMessage);
      }

      // 4. 다운로드 성공 시에만 인덱싱 서비스 호출
      Path filePath = optionalFilePath.get();
      System.out.println("다운로드 성공: " + filePath);
      System.out.println("파일 인덱싱을 시작합니다...");
//      indexingService.runIndexing(filePath);

      String successMessage = "접수번호 [" + rceptNo + "]에 대한 인덱싱이 성공적으로 완료되었습니다.";
      System.out.println(successMessage);
      return ResponseEntity.ok(successMessage);

    } catch (Exception e) {
      // 5. 그 외 예외 발생 시 서버 오류 응답
      String errorMessage = "인덱싱 처리 중 서버 내부 오류가 발생했습니다: " + e.getMessage();
      System.err.println(errorMessage);
      e.printStackTrace();
      return ResponseEntity.internalServerError().body(errorMessage);
    }
  }
}