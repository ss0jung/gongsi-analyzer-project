package com.sjproject.gongsianalyzer.dto;

import java.time.LocalDateTime;
import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SummaryResponseDto {
  private String rceptNo;           // 접수번호
  private String summary;           // 요약 내용
  private List<String> keywords;    // 핵심 키워드
  private Double confidence;        // 신뢰도 점수
  private LocalDateTime createdAt;  // 생성 시간
  private String status;            // SUCCESS, FAILED 등
}
