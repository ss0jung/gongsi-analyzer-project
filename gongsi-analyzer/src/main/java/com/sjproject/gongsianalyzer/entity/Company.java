package com.sjproject.gongsianalyzer.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Getter
@Setter
@Entity
public class Company {
    @Id
    private String corpCode;  // 공시대상회사의 고유번호(8자리) (PK)
    private String corpName;  // 정식회사명칭
    private String stockCode; // 상장회사인 경우 주식의 종목코드(6자리)

}
