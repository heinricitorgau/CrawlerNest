package clawer.service;

import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service for handling University-related business logic.
 */
@Service
public class UniversityService {

    private final UniversityRepository universityRepository;

    public UniversityService(UniversityRepository universityRepository) {
        this.universityRepository = universityRepository;
    }

    public List<University> getAllUniversities() {
        return universityRepository.findAll();
    }

    public University getUniversityById(String id) {
        return universityRepository.findById(id).orElse(null);
    }
}
