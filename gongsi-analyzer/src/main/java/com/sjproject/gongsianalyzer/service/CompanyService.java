package com.sjproject.gongsianalyzer.service;

import com.sjproject.gongsianalyzer.dto.xml.CorpInfoDto;
import com.sjproject.gongsianalyzer.dto.xml.ResultDto;
import com.sjproject.gongsianalyzer.entity.Company;
import com.sjproject.gongsianalyzer.repository.CompanyRepository;
import jakarta.xml.bind.JAXBContext;
import jakarta.xml.bind.Unmarshaller;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Slf4j
@Service
public class CompanyService {

  @Value("${dart.api.key}")
  private String dartApiKey;

  private static final String DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml";

  private final CompanyRepository companyRepository;
  private final WebClient fileDownloadWebClient;

  public CompanyService(CompanyRepository companyRepository, @Qualifier("fileDownloadWebClient") WebClient fileDownloadWebClient) {
    this.companyRepository = companyRepository;
    this.fileDownloadWebClient = fileDownloadWebClient;
  }

  public List<Company> searchByCorpName(String name){
    if(name == null || name.trim().isEmpty()){
      return  Collections.emptyList();
    }

    return companyRepository.findByCorpNameContainingIgnoreCase(name);
  }

  /**
   * DART API를 호출하여 전체 기업 코드를 DB에 업데이트하는 핵심 로직
   */
  public void updateCompanyDatabase() {
    log.info("DART 기업 고유번호 데이터베이스 업데이트를 시작합니다. (WebClient 사용)");

    try {
      // 1. DART API 호출해서 CORPCODE.zip 다운로드
      byte[] zippedBytes = downloadCorpCodeZip().block();
      if (zippedBytes == null) {
        log.error("기업 코드 ZIP 파일 다운로드에 실패했습니다.");
        return;
      }

      // 2. ZIP 파일 압축 해제
      InputStream xmlInputStream = unzipCorpCodeXml(zippedBytes);
      if (xmlInputStream == null) {
        log.error("ZIP 파일에서 CORPCODE.xml을 찾거나 여는 데 실패했습니다.");
        return;
      }

      // 3. XML 파일 파싱
      List<CorpInfoDto> corpInfoDtos = parseXml(xmlInputStream);

      // 4. 파싱된 데이터를 Company 엔티티 리스트로 변환
      List<Company> companies = corpInfoDtos.stream()
          .map(corpInfoDto -> new Company(
              corpInfoDto.getCorpCode(),
              corpInfoDto.getCorpName(),
              (corpInfoDto.getStockCode() != null && !corpInfoDto.getStockCode().trim().isEmpty()) ? corpInfoDto.getStockCode().trim() : null
          ))
          .collect(Collectors.toList());

      // 5. 파싱된 데이터를 DB에 저장
      companyRepository.deleteAllInBatch();
      companyRepository.saveAll(companies);

      log.info("총 {}개의 기업 정보 업데이트를 성공적으로 완료했습니다.", companies.size());

    } catch (Exception e) {
      log.error("기업 정보 업데이트 중 심각한 오류 발생", e);
    }
  }

  /**
   * WebClient를 사용하여 DART API로부터 기업 코드 ZIP 파일을 비동기적으로 다운로드합니다.
   */
  private Mono<byte[]> downloadCorpCodeZip() {
    return fileDownloadWebClient.get()
        .uri(DART_CORP_CODE_URL, uriBuilder -> uriBuilder.queryParam("crtfc_key", dartApiKey).build())
        .retrieve()
        .bodyToMono(byte[].class);
  }

  /**
   * ZIP 파일의 byte 배열을 받아 압축을 풀고, 내부의 CORPCODE.xml 파일에 대한 InputStream을 반환합니다.
   */
  private InputStream unzipCorpCodeXml(byte[] zippedBytes) throws Exception {
    try (ZipInputStream zipInputStream = new ZipInputStream(new ByteArrayInputStream(zippedBytes))) {
      ZipEntry entry;
      while ((entry = zipInputStream.getNextEntry()) != null) {
        if ("CORPCODE.xml".equals(entry.getName())) {
          ByteArrayOutputStream baos = new ByteArrayOutputStream();
          byte[] buffer = new byte[1024];
          int len;
          while ((len = zipInputStream.read(buffer)) > 0) {
            baos.write(buffer, 0, len);
          }
          return new ByteArrayInputStream(baos.toByteArray());
        }
      }
    }
    return null;
  }

  /**
   * XML InputStream을 파싱하여 CorpInfo 리스트로 변환합니다.
   */
  private List<CorpInfoDto> parseXml(InputStream inputStream) throws Exception {
    JAXBContext jaxbContext = JAXBContext.newInstance(ResultDto.class);
    Unmarshaller unmarshaller = jaxbContext.createUnmarshaller();
    ResultDto resultDto = (ResultDto) unmarshaller.unmarshal(inputStream);
    return resultDto.getList();
  }

  /**
   * 매일 새벽 4시에 주기적으로 실행되는 스케줄링 메서드
   */
  @Scheduled(cron = "0 0 4 * * *")
  public void scheduleCompanyDatabaseUpdate() {
    log.info("스케줄링된 기업 정보 업데이트를 실행합니다.");
    updateCompanyDatabase();
  }
}
