package clawer.api;

import clawer.dto.ApiResponse;
import clawer.service.DataQualityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/diagnostics/data-quality")
public class DataQualityController {

    private final DataQualityService dataQualityService;

    public DataQualityController(DataQualityService dataQualityService) {
        this.dataQualityService = dataQualityService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, Object>>> getDataQuality() {
        return ResponseEntity.ok(ApiResponse.success(dataQualityService.getDataQuality()));
    }
}
