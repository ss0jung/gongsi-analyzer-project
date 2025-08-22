package com.sjproject.gongsianalyzer.dto.xml;

import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;
import java.util.List;

@XmlRootElement(name = "result")
public class Result {
 private List<CorpInfo> list;

 @XmlElement(name = "list")
 public List<CorpInfo> getList() {
  return list;
 }

 public void setList(List<CorpInfo> list) {
  this.list = list;
 }
}