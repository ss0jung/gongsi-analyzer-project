package com.sjproject.gongsianalyzer.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class DisclosureSearchRequestDto {
  @NotBlank(message = "기업 정보가 전달되지 않았습니다.")
  private String corpCode;     // 고유번호
  private String beginDe;      // 시작일 (YYYYMMDD)
  private String endDe;        // 종료일 (YYYYMMDD)
  private String pblntfTy;     // 공시유형 (A, B, D)
}
