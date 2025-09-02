package com.sjproject.analyzerapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import lombok.Data;

@Data
public class DartApiResponseDto {
  private String status;
  private String message;

  @JsonProperty("list")
  private List<DartDisclosureDto> disclosures;

  @Data
  public static class DartDisclosureDto {
    @JsonProperty("rcept_no")
    private String rceptNo;

    @JsonProperty("report_nm")
    private String reportNm;

    @JsonProperty("rcept_dt")
    private String rceptDt;

    @JsonProperty("corp_name")
    private String corpName;

    @JsonProperty("corp_code")
    private String corpCode;

    @JsonProperty("corp_cls")
    private String corpCls;

    @JsonProperty("flr_nm")
    private String flrNm;

    @JsonProperty("rm")
    private String rm;
  }
}
