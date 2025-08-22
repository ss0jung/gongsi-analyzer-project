package com.sjproject.gongsianalyzer.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class IndexingRequest {
  @NotBlank(message = "접수번호는 필수입니다.")
  private String rceptNo;
}
