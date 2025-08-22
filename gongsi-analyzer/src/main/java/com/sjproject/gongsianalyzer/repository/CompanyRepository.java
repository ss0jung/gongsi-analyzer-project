package com.sjproject.gongsianalyzer.repository;

import com.sjproject.gongsianalyzer.entity.Company;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CompanyRepository extends JpaRepository<Company,String> {
  // 이름에 특정 문자열을 포함하는 회사 목록 검색 (대소문자 무시)
  List<Company> findByCorpNameContainingIgnoreCase(String name);
}
