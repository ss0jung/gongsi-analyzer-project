package com.sjproject.gongsianalyzer.config;

import com.sjproject.gongsianalyzer.repository.CompanyRepository;
import com.sjproject.gongsianalyzer.service.CompanyService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * 애플리케이션 시작 시 데이터베이스를 확인하고,
 * 비어있을 경우에만 DART 기업 정보를 초기화하는 클래스.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DataInitializer implements ApplicationRunner {

  private final CompanyRepository companyRepository;
  private final CompanyService companyService;

  @Override
  public void run(ApplicationArguments args) throws Exception {
    // DB의 company 테이블에 데이터가 하나도 없을 때만 초기화 로직을 수행합니다.
    if (companyRepository.count() == 0) {
      log.info("회사 정보 데이터베이스가 비어있어 초기화를 시작합니다.");
      try {
        companyService.updateCompanyDatabase();
        log.info("회사 정보 초기화가 성공적으로 완료되었습니다.");
      } catch (Exception e) {
        log.error("회사 정보 초기화 중 오류가 발생했습니다.", e);
      }
    } else {
      // 데이터가 이미 있다면, 불필요한 작업을 막기 위해 건너뜁니다.
      log.info("회사 정보가 이미 존재하므로 초기화를 건너뜁니다.");
    }
  }
}
