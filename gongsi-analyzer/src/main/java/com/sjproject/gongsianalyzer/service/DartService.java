package com.sjproject.gongsianalyzer.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Optional;
import java.util.zip.ZipInputStream;

@Service
public class DartService {

  @Value("${dart.api.key}")
  private String dartApiKey;

  private final RestTemplate restTemplate = new RestTemplate();
  private static final String DART_API_URL = "https://opendart.fss.or.kr/api/document.xml";
  // 저장될 디렉터리 경로
  private static final String SAVE_DIRECTORY = "disclosures_data";

  /**
   * DART API로부터 공시 문서를 Zip 파일로 다운로드하여 압축을 해제하고,
   * 내부의 원본 XML 파일 경로를 반환합니다.
   *
   * @param rceptNo 접수번호
   * @return 압축 해제된 원본 공시 파일의 Path. 실패 시 Optional.empty()
   */
  public Optional<Path> downloadDisclosure(String rceptNo) {
    String url = String.format("%s?crtfc_key=%s&rcept_no=%s", DART_API_URL, dartApiKey, rceptNo);
    System.out.println("호출 URL: "+ url);

    try {
      // 1. API 응답을 텍스트가 아닌 byte 배열(바이너리)로 받습니다.
      byte[] zippedBytes = restTemplate.getForObject(url, byte[].class);

      // API가 오류를 반환했는지 확인 (오류 응답은 보통 텍스트 XML)
      if (zippedBytes == null || new String(zippedBytes).contains("<status>")) {
        System.err.println("DART API로부터 유효하지 않은 응답을 받았습니다. 접수번호: " + rceptNo);
        return Optional.empty();
      }

      // 2. 다운로드한 byte 배열을 .zip 파일로 저장합니다.
      Path zipFilePath = Paths.get(SAVE_DIRECTORY, rceptNo + ".zip");
      Files.createDirectories(zipFilePath.getParent());
      Files.write(zipFilePath, zippedBytes);
      System.out.println("Zip 파일 저장 완료: " + zipFilePath);

      // 3. 저장된 Zip 파일의 압축을 풀고, 내부의 원본 XML 파일 경로를 가져옵니다.
      return unzipAndGetContentFile(zipFilePath, rceptNo);

    } catch (Exception e) {
      System.err.println("공시 문서 다운로드 및 압축 해제 중 오류 발생: " + e.getMessage());
      e.printStackTrace();
      return Optional.empty();
    }
  }

  /**
   * Zip 파일의 압축을 풀고 내부의 *.xml 파일을 찾아 경로를 반환합니다.
   * @param zipFilePath 압축 파일 경로
   * @param rceptNo 접수번호 (압축 해제 폴더명으로 사용)
   * @return 원본 파일 경로
   * @throws IOException 파일 처리 오류
   */
  private Optional<Path> unzipAndGetContentFile(Path zipFilePath, String rceptNo) throws IOException {
    // 압축을 해제할 대상 디렉터리 (예: disclosures_data/20190401004781/)
    Path destDir = Paths.get(SAVE_DIRECTORY, rceptNo);
    if (!Files.exists(destDir)) {
      Files.createDirectory(destDir);
    }

    Path originalFilePath = null;

    // ZipInputStream을 사용하여 압축 해제
    try (ZipInputStream zis = new ZipInputStream(Files.newInputStream(zipFilePath))) {
      var zipEntry = zis.getNextEntry();
      while (zipEntry != null) {
        Path newFilePath = destDir.resolve(zipEntry.getName());
        // 디렉터리인 경우 생성
        if (zipEntry.isDirectory()) {
          Files.createDirectories(newFilePath);
        } else {
          // 파일인 경우 내용 쓰기
          try (FileOutputStream fos = new FileOutputStream(newFilePath.toFile())) {
            fos.write(zis.readAllBytes());
          }
          // 원본 파일(.xml) 경로 저장
          if (newFilePath.toString().toLowerCase().endsWith(".xml")) {
            originalFilePath = newFilePath;
            System.out.println("압축 해제 및 원본 파일 확인: " + originalFilePath);
          }
        }
        zipEntry = zis.getNextEntry();
      }
    }

    // 임시로 사용된 zip 파일은 삭제
    Files.delete(zipFilePath);

    return Optional.ofNullable(originalFilePath);
  }
}