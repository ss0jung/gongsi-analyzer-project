package com.sjproject.analyzerapi.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class QueryRequestDto {
    @NotBlank(message = "질문은 필수 사항입니다.")
    private String question;
}
