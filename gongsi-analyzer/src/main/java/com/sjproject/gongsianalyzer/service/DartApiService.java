package com.sjproject.gongsianalyzer.service;

import com.sjproject.gongsianalyzer.dto.DartApiResponseDto;
import com.sjproject.gongsianalyzer.dto.DisclosureSearchRequestDto;
import com.sjproject.gongsianalyzer.dto.DisclosureSearchResponseDto;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;
import java.util.zip.ZipInputStream;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

@Slf4j
@Service
public class DartApiService {

  @Value("${dart.api.key}")
  private String dartApiKey;

  private static final String SAVE_DIRECTORY = "disclosures_data";    // 파일 저장 디렉토리 경로
  private static final String DART_API_URL = "https://opendart.fss.or.kr/api/document.xml";
  private static final Duration TIMEOUT = Duration.ofSeconds(30);

  private final WebClient dartApiWebClient;
  private final WebClient fileDownloadWebClient;

  public DartApiService(@Qualifier("dartApiWebClient") WebClient dartApiWebClient, @Qualifier("fileDownloadWebClient") WebClient fileDownloadWebClient) {
    this.dartApiWebClient = dartApiWebClient;
    this.fileDownloadWebClient = fileDownloadWebClient;
  }

  /**
   * DART API로부터 공시 문서를 Zip 파일로 다운로드하여 압축을 해제하고,
   * 내부의 원본 XML 파일 경로를 반환합니다.
   *
   * @param rceptNo 접수번호
   * @return 압축 해제된 원본 공시 파일의 Path. 실패 시 Optional.empty()
   */
  public Optional<Path> downloadDisclosure(String rceptNo) {
    String url = String.format("%s?crtfc_key=%s&rcept_no=%s", DART_API_URL, dartApiKey, rceptNo);
    log.info("호출 URL : {}", url);

    try {
      // 1. API 응답을 텍스트가 아닌 byte 배열(바이너리)로 받습니다.
      byte[] zippedBytes = fileDownloadWebClient.get()
          .uri(url)
          .retrieve()
          .bodyToMono(byte[].class)
          .block();

      // API가 오류를 반환했는지 확인 (오류 응답은 보통 텍스트 XML)
      if (zippedBytes == null || new String(zippedBytes).contains("<status>")) {
        log.error("DART API로부터 유효하지 않은 응답을 받았습니다. 접수번호: {}", rceptNo);
        return Optional.empty();
      }

      // 2. 다운로드한 byte 배열을 .zip 파일로 저장합니다.
      Path zipFilePath = Paths.get(SAVE_DIRECTORY, rceptNo + ".zip");
      Files.createDirectories(zipFilePath.getParent());
      Files.write(zipFilePath, zippedBytes);
      log.info("Zip 파일 저장 완료 : {}", zipFilePath);

      // 3. 저장된 Zip 파일의 압축을 풀고, 내부의 원본 XML 파일 경로를 가져옵니다.
      return unzipAndGetContentFile(zipFilePath, rceptNo);

    } catch (Exception e) {
      log.error("공시 문서 다운로드 및 압축 해제 중 오류 발생: {}", e.getMessage());
//      e.printStackTrace();
      return Optional.empty();
    }
  }

  /**
   * Zip 파일의 압축을 풀고 내부의 *.xml 파일을 찾아 경로를 반환합니다.
   * @param zipFilePath 압축 파일 경로
   * @param rceptNo 접수번호 (압축 해제 폴더명으로 사용)
   * @return 원본 파일 경로
   * @throws IOException 파일 처리 오류
   */
  private Optional<Path> unzipAndGetContentFile(Path zipFilePath, String rceptNo) throws IOException {
    // 압축을 해제할 대상 디렉터리 (예: disclosures_data/20190401004781/)
    Path destDir = Paths.get(SAVE_DIRECTORY, rceptNo);
    Files.createDirectories(destDir);

    Path originalFilePath = null;

    // ZipInputStream을 사용하여 압축 해제
    try (ZipInputStream zis = new ZipInputStream(Files.newInputStream(zipFilePath))) {
      var zipEntry = zis.getNextEntry();
      while (zipEntry != null) {
        Path newFilePath = destDir.resolve(zipEntry.getName());
        // 디렉터리인 경우 생성
        if (zipEntry.isDirectory()) {
          Files.createDirectories(newFilePath);
        } else {
          // 파일인 경우 내용 쓰기
          try (FileOutputStream fos = new FileOutputStream(newFilePath.toFile())) {
            fos.write(zis.readAllBytes());
          }
          // 원본 파일(.xml) 경로 저장
          if (newFilePath.toString().toLowerCase().endsWith(".xml")) {
            originalFilePath = newFilePath;
            log.info("압축 해제 및 원본 파일 확인:{} ", originalFilePath);
          }
        }
        zipEntry = zis.getNextEntry();
      }
    }

    // 임시로 사용된 zip 파일은 삭제
    Files.delete(zipFilePath);

    return Optional.ofNullable(originalFilePath);
  }

  public List<DisclosureSearchResponseDto> searchDisclosures(DisclosureSearchRequestDto request) {
    try {
      log.info("DART API 공시 검색 시작 - 기업코드: {}, 기간: {}~{}, 공시유형: {}",
          request.getCorpCode(), request.getBeginDe(), request.getEndDe(), request.getPblntfTy());

      // WebClient로 비동기 API 호출 후 동기로 변환
      DartApiResponseDto response = dartApiWebClient
          .get()
          .uri(uriBuilder -> uriBuilder
              .path("/list.json")
              .queryParam("crtfc_key", dartApiKey)
              .queryParam("corp_code", request.getCorpCode())
              .queryParam("bgn_de", request.getBeginDe())
              .queryParam("end_de", request.getEndDe())
              .queryParam("pblntf_ty", request.getPblntfTy())
              .queryParam("page_no", "1")
              .queryParam("page_count", "100")
              .build())
          .retrieve()
          .onStatus(
              httpStatus -> !httpStatus.is2xxSuccessful(),
              clientResponse -> {
                log.error("DART API HTTP 오류: {} - {}",
                    clientResponse.statusCode().value(),
                    clientResponse.statusCode().toString());
                return Mono.error(new RuntimeException(
                    "DART API 호출 실패: " + clientResponse.statusCode()));
              }
          )
          .bodyToMono(DartApiResponseDto.class)
          .timeout(TIMEOUT)
          .doOnError(WebClientResponseException.class, ex ->
              log.error("DART API WebClient 오류: {} - {}", ex.getStatusCode(), ex.getMessage()))
          .doOnError(Exception.class, ex ->
              log.error("DART API 호출 중 예상치 못한 오류", ex))
          .block(); // 비동기를 동기로 변환

      if (response == null) {
        log.warn("DART API 응답이 null입니다.");
        return List.of();
      }

      // DART API 상태 코드 확인
      if (!"000".equals(response.getStatus())) {
        log.error("DART API 비즈니스 오류: {} - {}", response.getStatus(), response.getMessage());
        return List.of();
      }

      // 공시 데이터 변환
      if (response.getDisclosures() == null || response.getDisclosures().isEmpty()) {
        log.info("검색된 공시가 없습니다.");
        return List.of();
      }

      List<DisclosureSearchResponseDto> results = response.getDisclosures().stream()
          .map(this::convertToDisclosureSearchResponse)
          .collect(Collectors.toList());

      log.info("DART API 검색 완료 - {} 건의 공시를 찾았습니다.", results.size());
      return results;

    } catch (Exception e) {
      log.error("공시 검색 중 오류 발생", e);
      throw new RuntimeException("공시 검색에 실패했습니다: " + e.getMessage(), e);
    }
  }

  private DisclosureSearchResponseDto convertToDisclosureSearchResponse(DartApiResponseDto.DartDisclosureDto dto) {
    return new DisclosureSearchResponseDto(
        dto.getRceptNo(),
        dto.getReportNm(),
        dto.getRceptDt(),
        dto.getCorpName(),
        dto.getCorpCode()
    );
  }
}