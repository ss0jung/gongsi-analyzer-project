package com.sjproject.gongsianalyzer.dto.xml;

import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;

@XmlRootElement(name="list")
public class CorpInfoDto {
  private String corpCode;
  private String corpName;
  private String stockCode;
  private String modifyDate;

  @XmlElement(name = "corp_code")
  public String getCorpCode() {
    return corpCode;
  }
  public void setCorpCode(String corpCode) {
    this.corpCode = corpCode;
  }

  @XmlElement(name = "corp_name")
  public String getCorpName() {
    return corpName;
  }
  public void setCorpName(String corpName) {
    this.corpName = corpName;
  }

  @XmlElement(name = "stock_code")
  public String getStockCode() {
    return stockCode;
  }
  public void setStockCode(String stockCode) {
    this.stockCode = stockCode;
  }

  @XmlElement(name = "modify_date")
  public String getModifyDate() {
    return modifyDate;
  }
  public void setModifyDate(String modifyDate) {
    this.modifyDate = modifyDate;
  }
}
