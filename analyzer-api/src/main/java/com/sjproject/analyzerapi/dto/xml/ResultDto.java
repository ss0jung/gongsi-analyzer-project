package com.sjproject.analyzerapi.dto.xml;

import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;
import java.util.List;

@XmlRootElement(name = "result")
public class ResultDto {
 private List<CorpInfoDto> list;

 @XmlElement(name = "list")
 public List<CorpInfoDto> getList() {
  return list;
 }

 public void setList(List<CorpInfoDto> list) {
  this.list = list;
 }
}