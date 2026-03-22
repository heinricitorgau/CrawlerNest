package clawer.service;

import clawer.dto.RankingDTO;
import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Service for handling University-related business logic.
 */
@Service
public class UniversityService {

    private final UniversityRepository universityRepository;

    public UniversityService(UniversityRepository universityRepository) {
        this.universityRepository = universityRepository;
    }

    public List<UniversityDTO> getAllUniversities(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return universityRepository.findAll(pageable).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    public UniversityDTO getUniversityById(Long id) {
        return universityRepository.findById(id)
                .map(this::convertToDTO)
                .orElse(null);
    }

    private UniversityDTO convertToDTO(University university) {
        UniversityDTO dto = new UniversityDTO();
        dto.setId(university.getId());
        dto.setSchoolSlug(university.getSchoolSlug());
        dto.setDisplayName(university.getDisplayName());
        dto.setCityName(university.getCityName());
        dto.setWebsiteUrl(university.getWebsiteUrl());
        
        if (university.getCountry() != null) {
            dto.setCountryName(university.getCountry().getCountryName());
        }

        if (university.getRankings() != null) {
            dto.setRankings(university.getRankings().stream()
                .map(ranking -> {
                    RankingDTO rDto = new RankingDTO();
                    rDto.setSource(ranking.getRankingSource());
                    rDto.setType(ranking.getRankingType());
                    rDto.setYear(ranking.getRankingYear());
                    rDto.setRankStart(ranking.getRankStart());
                    rDto.setRankEnd(ranking.getRankEnd());
                    rDto.setScore(ranking.getScore());
                    return rDto;
                }).collect(Collectors.toList()));
        }
        
        return dto;
    }
}
