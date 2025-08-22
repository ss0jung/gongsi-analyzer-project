package com.sjproject.gongsianalyzer.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@NoArgsConstructor
@AllArgsConstructor
@Builder
@Data
public class DisclosureSearchResponseDto {
  private String rceptNo;   // 접수번호(14자리)
  private String reportNm;  // 보고서명
  private String rceptDt;   // 공시 접수일자(YYYYMMDD)
  private String corpName;  // 종목명(법인명)
  private String corpCode;  // 고유번호

 /* public DisclosureSearchResponseDto(String rceptNo, String reportNm, String rceptDt,
      String corpName,
      String corpCode) {
    this.rceptNo = rceptNo;
    this.reportNm = reportNm;
    this.rceptDt = rceptDt;
    this.corpName = corpName;
    this.corpCode = corpCode;
  }*/
}