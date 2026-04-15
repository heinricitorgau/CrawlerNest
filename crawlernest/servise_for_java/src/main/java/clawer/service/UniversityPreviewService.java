package clawer.service;

import clawer.dto.CanonicalUniversityDetailPreviewDTO;
import clawer.repository.UniversityPreviewRepository;
import org.springframework.stereotype.Service;

import java.util.Optional;

@Service
public class UniversityPreviewService {
    private final UniversityPreviewRepository universityPreviewRepository;

    public UniversityPreviewService(UniversityPreviewRepository universityPreviewRepository) {
        this.universityPreviewRepository = universityPreviewRepository;
    }

    public Optional<CanonicalUniversityDetailPreviewDTO> getPreview(Long canonicalUniversityId, String universityName) {
        if (canonicalUniversityId != null) {
            return universityPreviewRepository.findByCanonicalUniversityId(canonicalUniversityId);
        }
        return universityPreviewRepository.findByUniversityName(universityName);
    }
}
