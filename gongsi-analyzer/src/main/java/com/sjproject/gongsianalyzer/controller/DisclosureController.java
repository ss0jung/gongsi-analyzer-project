package com.sjproject.gongsianalyzer.controller;

import com.sjproject.gongsianalyzer.dto.ApiResponse;
import com.sjproject.gongsianalyzer.dto.DisclosureSearchRequestDto;
import com.sjproject.gongsianalyzer.dto.IndexingRequestDto;
import com.sjproject.gongsianalyzer.dto.QueryRequestDto;
import com.sjproject.gongsianalyzer.dto.DisclosureSearchResponseDto;
import com.sjproject.gongsianalyzer.entity.Company;
import com.sjproject.gongsianalyzer.service.CompanyService;
import com.sjproject.gongsianalyzer.service.DartApiService;
import com.sjproject.gongsianalyzer.service.IndexingService;
import com.sjproject.gongsianalyzer.service.QueryService;
import jakarta.validation.Valid;
import java.nio.file.Path;
import java.util.List;
import java.util.Optional;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/v1")
@Slf4j // Lombok 로깅
public class DisclosureController {

  private final DartApiService dartApiService;
  private final IndexingService indexingService;
  private final QueryService queryService;
  private final CompanyService companyService;

  public DisclosureController(
      DartApiService dartApiService,
      IndexingService indexingService,
      QueryService queryService,
      CompanyService companyService) {
    this.dartApiService = dartApiService;
    this.indexingService = indexingService;
    this.queryService = queryService;
    this.companyService = companyService;
  }

  /**
   * 기업명 검색 시, 자동 완성
   * */
  @GetMapping("/search/companies")
  public ResponseEntity<List<Company>> searchCompanies(@RequestParam("query") String query){
    List<Company> companies = companyService.searchByCorpName(query);
    return  ResponseEntity.ok(companies);
  }

  /**
   * 공시 검색
   */
  @PostMapping("/search")
  public ResponseEntity<List<DisclosureSearchResponseDto>> searchDisclosures(
      @Valid @RequestBody DisclosureSearchRequestDto request) {

    log.info("공시 검색 요청: 기업코드={}, 기간={}~{}, 공시유형={}",
        request.getCorpCode(), request.getBeginDe(), request.getEndDe(), request.getPblntfTy());

    try {
      List<DisclosureSearchResponseDto> results = dartApiService.searchDisclosures(request);

      log.info("검색 완료: {} 건의 공시를 찾았습니다.", results.size());

      return ResponseEntity.ok(results);

    } catch (Exception e) {
      log.error("공시 검색 실패", e);
      return ResponseEntity.internalServerError().build();
    }
  }

  /**
  * 공시보고서 전처리 + 요약본
  * */
  @PostMapping("/index")
  public ResponseEntity<ApiResponse> startIndexing(@Valid @RequestBody IndexingRequestDto request) {
    String rceptNo = request.getRceptNo();

    try {
      log.info("접수번호 [{}] 공시 데이터 다운로드 시작", rceptNo);

      Optional<Path> optionalFilePath = dartApiService.downloadDisclosure(rceptNo);

      if (optionalFilePath.isEmpty()) {
        log.warn("공시 문서 다운로드 실패: {}", rceptNo);
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(ApiResponse.error("공시 문서를 찾을 수 없습니다"));
      }

      Path filePath = optionalFilePath.get();
      indexingService.triggerIndexingApi(filePath);
      log.info("접수번호 [{}] 인덱싱 완료", rceptNo);

      return ResponseEntity.ok(ApiResponse.success("인덱싱이 완료되었습니다", null));

    } catch (Exception e) {
      log.error("인덱싱 처리 중 오류 발생: {}", e.getMessage(), e);
      return ResponseEntity.internalServerError()
          .body(ApiResponse.error("서버 내부 오류가 발생했습니다"));
    }
  }

  /**
  * 질문 처리 및 답변 반환
  * */
  @PostMapping("/query")
  public Mono<ResponseEntity<ApiResponse>> getAnswer(@Valid @RequestBody QueryRequestDto request) {
    return queryService.getAnswerFromPython(request.getQuestion())
        .map(result -> ResponseEntity.ok(ApiResponse.success("RAG 답변 생성 완료", result)))
        .onErrorResume(e -> {
          log.error("질문 처리 중 오류: {}", e.getMessage(), e);
          return Mono.just(ResponseEntity.internalServerError()
              .body(ApiResponse.error("답변 생성 중 오류가 발생했습니다")));
        });
  }


}